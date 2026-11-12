from fastapi import APIRouter
from fastapi import APIRouter,Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Query
from sqlalchemy import select
from fastapi import HTTPException
from toutiao_backend.models.users import User
from toutiao_backend.config.db_conf import get_db
from toutiao_backend.utils.auth import get_current_user
from toutiao_backend.utils.response import success_response
from toutiao_backend.schemas.history import HistoryAddRequest,HistoryNewsItemResponse,HistoryListResponse
from toutiao_backend.models.history import History
from toutiao_backend.crud.history import crud_add_history,crud_get_history_list,crud_delete_history,crud_clear_history

history_router=APIRouter(prefix="/api/history",tags=["history"])
#添加浏览历史
@history_router.post("/add")
async def add_history(
    data:HistoryAddRequest,
    db:AsyncSession=Depends(get_db),
    current_user:User=Depends(get_current_user)
):
    result=await crud_add_history(db,data.news_id,current_user.id)
    return success_response(message="添加成功",data=result)

#获取浏览历史列表
@history_router.get("/list")
async def get_history_list(
    db:AsyncSession=Depends(get_db),
    current_user:User=Depends(get_current_user),
    page:int=Query(1,ge=1),
    page_size:int=Query(10,ge=1,le=100,alias="pageSize"),
):
    history_list,total_count=await crud_get_history_list(db,current_user.id,page,page_size)
    has_more=total_count>page*page_size
    response=[HistoryNewsItemResponse.model_validate({
       **news.__dict__, #这里的小news是实例对象，需要转换为字典
       "view_time":view_time,
       "history_id":history_id,
    }) for news,view_time,history_id in history_list]
    data=HistoryListResponse(
        list=response,
        total=total_count,
        has_more=has_more
    )
    return success_response(message="获取成功",data=data)

#删除一条浏览历史
@history_router.delete("/delete/{news_id}")
async def delete_history(
    news_id:int,
    db:AsyncSession=Depends(get_db),
    current_user:User=Depends(get_current_user)
):
    result=await crud_delete_history(db,news_id,current_user.id)
    if not result:
        raise HTTPException(status_code=404,detail="历史记录不存在")
    return success_response(message="删除成功",data=result)

#删除所有浏览历史
@history_router.delete("/clear")
async def clear_history(
    db:AsyncSession=Depends(get_db),
    current_user:User=Depends(get_current_user)
):
    await crud_clear_history(db,current_user.id)
    return success_response(message="删除成功")
