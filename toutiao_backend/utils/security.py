from passlib.context import CryptContext

#创建密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#密码加密
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

#密码解密
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)