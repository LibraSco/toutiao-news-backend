from toutiao_backend.models.favourite import Favorite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,delete,func
from toutiao_backend.models.news import News

#检查用户是否收藏了新闻
async def crud_is_favourite(db:AsyncSession,user_id:int,news_id:int):
    query = select(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

#添加收藏
async def crud_add_favourite(db:AsyncSession,user_id:int,news_id:int):
    favourite = Favorite(user_id=user_id,news_id=news_id)
    db.add(favourite)
    await db.commit()
    await db.refresh(favourite)
    return favourite

#取消收藏
async def crud_remove_favourite(db:AsyncSession,user_id:int,news_id:int):
    delete_query = delete(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    result = await db.execute(delete_query)
    await db.commit()
    return result.rowcount > 0  

#获取用户收藏的新闻列表
async def crud_get_favourite_list(db:AsyncSession,user_id:int,page:int=1,page_size:int=10):
   #总量+收藏的新闻列表
   count_query=select(func.count()).where(Favorite.user_id == user_id)
   count_result=await db.execute(count_query)
   total=count_result.scalar_one_or_none()
   #获取收藏列表-联表查询+收藏时间排序+分页
   query=select(News,Favorite.create_at.label("favorite_time"),Favorite.id.label("favorite_id")).join(Favorite,Favorite.news_id==News.id).where(Favorite.user_id == user_id).order_by(Favorite.create_at.desc()).offset((page-1)*page_size).limit(page_size)
        
   result=await db.execute(query)
   rows=result.all()
   return rows,total

async def crud_clear_favourite(db:AsyncSession,user_id:int):
    delete_query = delete(Favorite).where(Favorite.user_id == user_id)
    result = await db.execute(delete_query)
    await db.commit()
    return result.rowcount or 0
