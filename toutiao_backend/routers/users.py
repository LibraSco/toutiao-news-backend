from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from toutiao_backend.config.db_conf import get_db
from toutiao_backend.models.users import User
from toutiao_backend.utils.auth import get_current_user
from toutiao_backend.schemas.users import UserRequest,UserAuthResponse,UserInfoResponse
from toutiao_backend.utils.response import success_response
from toutiao_backend.crud.users import crud_create_user,crud_get_user_by_username,crud_generate_token,authenticate_user,crud_update_user_info,crud_change_password
from toutiao_backend.schemas.users import UpdateUserInfoRequest,ChangePasswordRequest


#以后在路由函数中只要考虑正确的query参数，不需要考虑异常处理
users_router=APIRouter(prefix="/api/user",tags=["user"])

@users_router.post("/register")
async def register(user: UserRequest, db: AsyncSession = Depends(get_db)):
    #注册逻辑：验证用户是否存在-》创建用户-》返回token
    existing_user = await crud_get_user_by_username(db, user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户已存在")

    created_user = await crud_create_user(db, user_data=user)
    token = await crud_generate_token(db, created_user.id)

    return {
        "code": 200,
        "message": "注册成功",
        "data": {
            "token": token.token,
            "userInfo": {
            "id": created_user.id,
            "username": created_user.username,
            "nickname": created_user.nickname,
            "avatar": created_user.avatar,
            "bio": created_user.bio
            }
        }
    }

@users_router.post("/login")
async def login(user: UserRequest, db: AsyncSession = Depends(get_db)):
    #登录逻辑：验证用户是否存在-》验证密码-》返回token->返回成功响应
    user_result=await authenticate_user(db,user.username,user.password)
    if not user_result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = await crud_generate_token(db,user_result.id)
    response_data=UserAuthResponse(token=token.token,user_info=UserInfoResponse.model_validate(user_result))
    return success_response(message="登录成功",data=response_data)

#获取用户信息,使用依赖注入获取当前用户
@users_router.get("/info")
async def get_user_info(current_user:User=Depends(get_current_user)):
    return success_response(message="用户信息获取成功",data=UserInfoResponse.model_validate(current_user))

#更新用户信息:验证token->更新用户信息->返回成功响应
@users_router.put("/update")
async def update_user_info(user_data: UpdateUserInfoRequest, user:User=Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    #更新用户信息逻辑：验证用户是否存在-》更新用户信息-》返回成功响应
    updated_user = await crud_update_user_info(db, user.username, user_data)
    return success_response(message="用户信息更新成功",data=UserInfoResponse.model_validate(updated_user))
    
#更改用户密码
@users_router.put("/password")
async def change_password(change_password: ChangePasswordRequest, user:User=Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    #更改用户密码逻辑：验证用户是否存在-》验证旧密码-》更新新密码-》返回成功响应
    if not await crud_change_password(db,user,change_password.old_password,change_password.new_password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    return success_response(message="密码更新成功")