from fastapi import APIRouter,Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Query
from sqlalchemy import select
from toutiao_backend.models.users import User
from toutiao_backend.config.db_conf import get_db
from fastapi import HTTPException
from toutiao_backend.utils.auth import get_current_user
from toutiao_backend.crud.favourite import crud_is_favourite,crud_add_favourite,crud_remove_favourite,crud_get_favourite_list,crud_clear_favourite
from toutiao_backend.utils.response import success_response
from toutiao_backend.schemas.favourite import FavoriteCheckResponse,FavoriteAddRequest
from toutiao_backend.models.favourite import Favorite
from toutiao_backend.schemas.favourite import FavoriteListResponse


favorite_router = APIRouter(prefix="/api/favorite",tags=["favorite"])

@favorite_router.get("/check")
async def check_favourite(db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user),news_id:int=Query(...,alias="newsId")):
    #查询用户是否收藏了该新闻
    result = await crud_is_favourite(db,user.id,news_id)
    return success_response(message="检查收藏状态成功",data=FavoriteCheckResponse(isFavorite=result))

@favorite_router.post("/add")
async def add_favourite(data:FavoriteAddRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    #添加收藏
    result=await crud_add_favourite(db,user.id,data.news_id)
    return success_response(message="添加收藏成功",data=result)

#  取消收藏
@favorite_router.delete("/remove")
async def remove_favourite(news_id:int=Query(...,alias="newsId"),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    result=await crud_remove_favourite(db,user.id,news_id)
    if not result:
        raise HTTPException(status_code=404,detail="用户未收藏该新闻")
    return success_response(message="取消收藏成功")

#  获取用户收藏的新闻列表
@favorite_router.get("/list")
async def get_favourite_list(page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100,alias="pageSize"),db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    #查询用户收藏的新闻列表
    rows,total=await crud_get_favourite_list(db,user.id,page,page_size)
    favorite_list=[{**news.__dict__,
                    "favorite_time":favorite_time,
                    "favorite_id":favorite_id,
                    } for news,favorite_time,favorite_id in rows]
    has_more=total>page*page_size
    return success_response(message="获取收藏列表成功",data=FavoriteListResponse(list=favorite_list,total=total,has_more=has_more))

#清空用户的收藏列表
@favorite_router.delete("/clear")
async def clear_favourite(db:AsyncSession=Depends(get_db),user:User=Depends(get_current_user)):
    #清空用户收藏的新闻列表
    count=await crud_clear_favourite(db,user.id)
    return success_response(message=f"清空共{count}条记录成功") #这里就不需要返回什么了

