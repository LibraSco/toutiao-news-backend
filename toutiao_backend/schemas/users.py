#用于做类型校验
from pydantic import BaseModel,Field,ConfigDict
from typing import Optional
class UserRequest(BaseModel):
    username:str=Field(...,min_length=3,max_length=20,description="用户名")
    password:str=Field(...,min_length=6,max_length=20,description="密码")

#user_info对应的类:基础类+可选类
class UserInfoBase(BaseModel):
    nickname:Optional[str]=Field(None,description="昵称")
    avatar:Optional[str]=Field(None,description="头像URL")  
    gender:Optional[str]=Field(None,description="性别")
    bio:Optional[str]=Field(None,description="个人简介")

class UserInfoResponse(UserInfoBase):
    id:int=Field(...,description="用户ID")
    username:str=Field(...,description="用户名")
    model_config = ConfigDict(
            from_attributes=True,  # 允许从ORM模型对象中读取数据
    )


#data数据类型
class UserAuthResponse(BaseModel):
    token:str=Field(...,description="用户token")
    user_info:UserInfoResponse=Field(...,description="用户信息",alias="userInfo")
    #模型类配置
    model_config = ConfigDict(
        from_attributes=True,  # 允许从ORM模型对象中读取数据
        populate_by_name=True,  # 允许通过字段名称进行赋值
    )

#更新用户信息的模型类
class UpdateUserInfoRequest(UserInfoBase):
    nickname:Optional[str]=Field(None,description="昵称")
    avatar:Optional[str]=Field(None,description="头像URL")  
    gender:Optional[str]=Field(None,description="性别")
    bio:Optional[str]=Field(None,description="个人简介")
    phone:Optional[str]=Field(None,description="手机号")

#修改用户密码
class ChangePasswordRequest(BaseModel):
    old_password:str=Field(...,min_length=6,max_length=20,alias="oldPassword",description="旧密码")
    new_password:str=Field(...,min_length=6,max_length=20,alias="newPassword",description="新密码")
