import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from toutiao_backend.cache.news_cache import (
    acquire_detail_lock,
    bump_list_version,
    delete_news_detail,
    delete_news_detail_later,
    get_list_version,
    get_news_categories,
    get_news_detail as get_news_detail_cache,
    get_news_list as get_news_list_cache,
    incr_news_views,
    init_news_views,
    news_to_dict,
    release_detail_lock,
    set_news_categories,
    set_news_detail as set_news_detail_cache,
    set_news_list as set_news_list_cache,
    set_news_null,
)
from toutiao_backend.config.db_conf import get_db
from toutiao_backend.crud.news import (
    crud_get_categories,
    crud_get_news_list,
    crud_get_news_count,
    crud_get_news_detail,
    crud_increment_news_views,
    crud_get_related_news,
    crud_update_news,
)
from toutiao_backend.models.users import User
from toutiao_backend.schemas.news import NewsUpdateRequest
from toutiao_backend.utils.auth import get_current_user

#创建APIRouter实例
router=APIRouter(prefix="/api/news",tags=["news"])
#接口实现流程
#1.模块化路由->API接口文档
#2.定义模型类-》数据库表
#3.在crud文件夹里创建文件，封装操作库的方法
#4.在路由处理函数里面调用crud封装好的方法，响应结果

def _detail_payload(news,related_news) -> dict:
    """详情字段和列表不同，前端要驼峰命名，这里统一转换一份给缓存和响应共用"""
    return {
        "id": news.id,
        "title": news.title,
        "content": news.content,
        "image": news.image,
        "author": news.author,
        "publishTime": news.publish_time.isoformat(),
        "categoryId": news.category_id,
        "views": news.views,
        "relatedNews": related_news,
    }

@router.get("/categories")
async def get_categories(skip:int=0,limit:int=100,db:AsyncSession=Depends(get_db)):
    cached = await get_news_categories() if skip==0 and limit==100 else None
    if cached is not None:
        return {"code":200,"messages":"success","data":cached}
    categories = await crud_get_categories(db,skip,limit)
    data=[news_to_dict(category) for category in categories]
    if skip==0 and limit==100:
        await set_news_categories(data)
    return {
        "code":200,
        "messages":"success",
        "data":data,
    }

@router.get("/list")
async def get_news_list(
    category_id:int=Query(alias="categoryId"),
    page:int=1,
    page_size:int=Query(10,alias="pageSize",le=100),
    last_publish_time:Optional[datetime]=Query(None,alias="lastPublishTime"),
    last_id:Optional[int]=Query(None,alias="lastId"),
    db:AsyncSession=Depends(get_db)
    ):
    #带游标走 keyset 分页：索引直接定位到上一页末尾之后，翻到 8000 页也不会变慢
    #不带游标且 page>1 时回退到 OFFSET，兼容老前端按页码翻页
    cursor = (last_publish_time,last_id) if last_publish_time and last_id else None
    offset = 0 if cursor else (page-1)*page_size

    if cursor:
        anchor=f'{cursor[0].isoformat()}:{cursor[1]}'
    elif offset:
        anchor=f'offset:{offset}'
    else:
        anchor='first'

    cached = await get_news_list_cache(category_id,page_size,anchor,await get_list_version())
    if cached is not None:
        return {"code":200,"messages":"获取新闻列表成功","data":cached}

    news_list,hasmore = await crud_get_news_list(db,category_id,page_size,cursor,offset)
    #COUNT 只在首屏算：翻页时用多取一条得到的 hasmore 就够了，不必每页再扫一遍全表
    total = await crud_get_news_count(db,category_id) if anchor=='first' else None
    next_cursor = None
    if hasmore and news_list:
        last = news_list[-1]
        next_cursor = {"publishTime":last.publish_time.isoformat(),"id":last.id}
    data={
        "list":[news_to_dict(news) for news in news_list],
        "total":total,
        "hasmore":hasmore,
        "nextCursor":next_cursor,
    }
    await set_news_list_cache(category_id,page_size,anchor,data,await get_list_version())
    return {
        "code":200,#响应成功状态码
        "messages":"获取新闻列表成功",
        "data":data,
    }

@router.get("/detail")
async def get_news_detail(news_id:int=Query(alias="id"),db:AsyncSession=Depends(get_db)):
    data = await get_news_detail_cache(news_id)
    if data is False:
        #命中空值缓存，直接返回，不用打数据库（防穿透）
        raise HTTPException(status_code=404,detail="新闻不存在")

    if data is None:
        #缓存没命中：只放一个请求回源重建，其余请求轮询等它写回缓存（防击穿）
        token = await acquire_detail_lock(news_id)
        if token is None:
            for _ in range(25):  #最多等 500ms，正常情况下第一个请求早就写完了
                await asyncio.sleep(0.02)
                data = await get_news_detail_cache(news_id)
                if data is not None:
                    break
        if data is False:
            raise HTTPException(status_code=404,detail="新闻不存在")
        if data is None:
            news_detail = await crud_get_news_detail(db,news_id)
            if not news_detail:
                await set_news_null(news_id)
                raise HTTPException(status_code=404,detail="新闻不存在")
            related_news = await crud_get_related_news(db,news_detail.id,news_detail.category_id)
            data = _detail_payload(news_detail,related_news)
            await set_news_detail_cache(news_id,data)
            await init_news_views(news_id,news_detail.views)
        if token:
            await release_detail_lock(news_id,token)

    views = await incr_news_views(news_id)
    if views is None:
        #Redis 不可用时退回数据库自增，浏览量不能丢
        await crud_increment_news_views(db,news_id)
        views = data.get("views",0)+1
    return {
        "code": 200,
        "messages": "success",
        "data": {**data,"views":views},
    }

@router.patch("/update")
async def update_news(
    data:NewsUpdateRequest,
    news_id:int=Query(...,alias="id"),
    user:User=Depends(get_current_user),
    db:AsyncSession=Depends(get_db),
    ):
    #教学项目没有角色体系，带合法 token 就能改；线上这里要补管理员权限校验
    #exclude_none：传 null 不算修改，免得把 NOT NULL 的 title/content 写成空
    fields=data.model_dump(exclude_unset=True,exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400,detail="没有需要更新的字段")
    news=await crud_update_news(db,news_id,fields)
    if not news:
        raise HTTPException(status_code=404,detail="新闻不存在")
    #先更新库再删缓存；延迟再删一次，清掉读请求可能回填的旧值
    await delete_news_detail(news_id)
    asyncio.create_task(delete_news_detail_later(news_id))
    #列表缓存的 key 带版本号，自增一下等于整类立即失效，不用挨个找 key 删
    await bump_list_version()
    return {"code":200,"messages":"更新成功","data":{"id":news_id,"title":news.title}}
