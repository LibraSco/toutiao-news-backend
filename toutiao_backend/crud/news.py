# 封装新闻分类CRUD操作
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_,func,or_,select,update
from toutiao_backend.models.news import Category,News #导入模型类

async def crud_get_categories(db:AsyncSession,skip:int=0,limit:int=100):
    stmt = select(Category).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def crud_get_news_list(
    db:AsyncSession,
    category_id:int,
    limit:int=10,
    cursor:Optional[Tuple[datetime,int]]=None,
    skip:int=0,
) -> Tuple[list,bool]:
    """返回 (当前页新闻, 是否还有下一页)。多取一条判断 hasmore，省掉一次 COUNT。"""
    stmt = select(News).where(News.category_id==category_id)
    if cursor is None:
        #兼容按页码翻页：OFFSET 要先扫过 skip 行再丢弃，深页会线性变慢
        stmt = stmt.offset(skip)
    else:
        last_publish_time, last_id = cursor
        #不用 (publish_time,id) < (x,y) 行构造器：实测这里退化成 ref 全扫，
        # 拆成字典序后优化器才走 range，8000 页从 41ms 降到 1ms
        stmt = stmt.where(
            or_(
                News.publish_time < last_publish_time,
                and_(
                    News.publish_time == last_publish_time,
                    News.id < last_id,
                ),
            )
        )
    stmt = stmt.order_by(
        News.publish_time.desc(),#发布时间降序
        News.id.desc()#同秒发布用 id 兜底，保证游标不重不漏
    ).limit(limit+1)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return rows[:limit], len(rows) > limit

#查询指定分类下的新闻数量
async def crud_get_news_count(db:AsyncSession,category_id:int):
    stmt = select(func.count(News.id)).where(News.category_id==category_id)
    result = await db.execute(stmt)
    return result.scalar_one() #返回单个结果

async def crud_get_news_detail(db:AsyncSession,news_id:int):
    stmt = select(News).where(News.id==news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() #返回单个结果或None,当查到就返回新闻对象，没查到就返回None

async def crud_increment_news_views(db:AsyncSession,news_id:int):
    stmt = update(News).where(News.id==news_id).values(views=News.views+1)
    result = await db.execute(stmt)
    await db.commit()
    #命中了新闻，返回True，没命中返回False
    return result.rowcount > 0

async def crud_set_news_views(db:AsyncSession,news_id:int,views:int):
    """缓存里的浏览量是绝对值，直接覆盖写，重复执行不会累加出错"""
    stmt = update(News).where(News.id==news_id).values(views=views)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

async def crud_update_news(db:AsyncSession,news_id:int,fields:dict):
    """只更新传了的字段；返回更新后的新闻，没这条则返回 None"""
    stmt = update(News).where(News.id==news_id).values(**fields,updated_at=datetime.now())
    result = await db.execute(stmt)
    if result.rowcount == 0:
        return None
    await db.commit()
    return await crud_get_news_detail(db,news_id)

#推荐相关新闻
async def crud_get_related_news(db:AsyncSession,news_id:int,category_id:int,limit:int=5):
    # 这里可以实现推荐相关新闻的逻辑，
    # 按照发布时间和浏览量排序
    stmt = select(News).where(
        News.id!=news_id,
        News.category_id==category_id
    ).order_by(
        News.publish_time.desc(),#发布时间降序
        News.views.desc()#浏览量降序
        ).limit(limit)
    result = await db.execute(stmt)
    related_news = result.scalars().all()
    #用列表推导式得到新闻的核心数据
    return [{
        "id":news.id,"title":news.title,
        "content":news.content,"image":news.image,
        "author":news.author,"publishTime":news.publish_time.isoformat(),
        "categoryId":news.category_id,"views":news.views
        } for news in related_news]
