from toutiao_backend.crud.users import crud_get_user_by_token
from fastapi import HTTPException,Header,Depends,status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from toutiao_backend.models.users import UserToken,User
from toutiao_backend.config.db_conf import get_db

#根据token查询用户，最终返回用户
async def get_current_user(authorization:str=Header(...,alias="Authorization"),db:AsyncSession=Depends(get_db)):
    #从header中获取token
    #从header中获取token（兼容带Bearer前缀和不带前缀的格式）
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    else:
        token = authorization
    #根据token查询用户
    user = await crud_get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的token")
    return user
