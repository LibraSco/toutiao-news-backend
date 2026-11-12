from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,delete,func
from toutiao_backend.models.news import News
from toutiao_backend.models.history import History
from toutiao_backend.models.users import User
from datetime import datetime

#添加浏览历史
async def crud_add_history(
    db: AsyncSession,
    news_id: int,
    user_id: int,
):
    """
    添加浏览历史
    """
    query = select(History).where(History.user_id == user_id, History.news_id == news_id)
    result = await db.execute(query)
    existing_history = result.scalar_one_or_none()
    if existing_history:
        existing_history.view_time = datetime.now()
        await db.commit()
        await db.refresh(existing_history)
        return existing_history
    else:
        history = History(user_id=user_id, news_id=news_id)
        db.add(history)
        await db.commit()
        await db.refresh(history)
        return history

#获取浏览历史列表
async def crud_get_history_list(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 10,
):
    """
    获取浏览历史列表
    """
    offset = (page - 1) * page_size
    count_query = select(func.count(History.id)).where(History.user_id == user_id)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()
    query = (select(News,History.view_time.label("view_time"),
                   History.id.label("history_id")).join(History,History.news_id == News.id).where(History.user_id == user_id).order_by(History.view_time.desc()).offset(offset).limit(page_size))
    result = await db.execute(query)
    history_list = result.all()
    return history_list,total_count

#删除一条浏览历史
async def crud_delete_history(
    db: AsyncSession,
    news_id: int,
    user_id: int,
):
    """
    删除一条浏览历史
    """
    query = delete(History).where(History.news_id == news_id, History.user_id == user_id)
    result = await db.execute(query)
    await db.execute(query)
    await db.commit()
    return result.rowcount>0

#删除所有浏览历史
async def crud_clear_history(
        db: AsyncSession,
        user_id: int,
):
    """
    删除所有浏览历史
    """
    query = delete(History).where(History.user_id == user_id)
    result = await db.execute(query)
    await db.execute(query)
    await db.commit()
    return result.rowcount or 0
