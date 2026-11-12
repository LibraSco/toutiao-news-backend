from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,update
from toutiao_backend.models.users import User,UserToken
from toutiao_backend.schemas.users import UserRequest,UpdateUserInfoRequest,ChangePasswordRequest
from toutiao_backend.utils.security import get_password_hash
import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
from toutiao_backend.utils.security import verify_password,get_password_hash
from toutiao_backend.utils.response import success_response

#根据用户名查询用户
async def crud_get_user_by_username(db:AsyncSession,username:str):
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    return result.scalar_one_or_none()

#创建用户
async def crud_create_user(db:AsyncSession,user_data:UserRequest):
    user_password = get_password_hash(user_data.password)
    user=User(
        username=user_data.username,
        password=user_password
    )
    db.add(user)
    await db.commit()
    await db.refresh(user) # 刷新用户对象,读回最新的用户信息
    return user

#生成token
async def crud_generate_token(db:AsyncSession,user_id:int):
    #生成token+设置过期时间-》查询当前数据库是否有token-》有则更新token和过期时间-》无则创建token
    token = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(days=7) # 设置过期时间为7天后
    query = select(UserToken).where(UserToken.user_id == user_id)
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()
    if user_token:
        user_token.token = token
        user_token.expires_at = expires_at
    else:
        user_token = UserToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        db.add(user_token) #这个是同步方法，不能异步操作
    await db.commit()
    return user_token

#检查用户是否有效
async def authenticate_user(db:AsyncSession,username:str,password:str):
    #查询用户是否存在-》验证密码是否正确-》返回token
    user = await crud_get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user

#根据token查询用户
async def crud_get_user_by_token(db:AsyncSession,token:str):
    query = select(UserToken).where(UserToken.token == token)
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()
    if not user_token or user_token.expires_at < datetime.now():
        return None
    query_user = select(User).where(User.id == user_token.user_id)
    result_user = await db.execute(query_user)
    return result_user.scalar_one_or_none()

#更新用户信息
async def crud_update_user_info(db:AsyncSession,username:str,user_data:UpdateUserInfoRequest):
    #查询用户是否存在-》更新用户信息-》返回更新后的用户信息
    #没有设置值的时候不更新，user_dat是一个pydantic类型，得到字典->**解包字典->更新用户信息
    query = update(User).where(User.username == username).values(**user_data.model_dump(
        exclude_unset=True,
        exclude_none=True
    ))
    result=await db.execute(query)
    await db.commit()
    #检查更新
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="用户不存在")
    #返回更新后的用户信息
    return await crud_get_user_by_username(db, username)

#更改用户密码
async def crud_change_password(db:AsyncSession,user:User,old_password:str,new_password:str):
    #查询用户是否存在-》验证旧密码-》更新新密码-》返回成功响应
    if not verify_password(old_password, user.password):
        return False
    Hash_password = get_password_hash(new_password)
    user.password = Hash_password
    db.add(user) #保证能提交到数据库
    await db.commit()
    await db.refresh(user) # 刷新用户对象,读回最新的用户信息
    return True