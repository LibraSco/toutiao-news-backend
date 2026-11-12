import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker,AsyncSession,create_async_engine

#连接串放 .env，不写死在代码里，开源时不会把数据库口令一起传上去
load_dotenv()
#数据库URL
ASYNC_DATABASE_URL=os.getenv("DATABASE_URL","")
if not ASYNC_DATABASE_URL:
    raise RuntimeError("缺少 DATABASE_URL，请复制 .env.example 为 .env 并填写数据库连接")
#创建异步引擎
async_engine=create_async_engine(
    ASYNC_DATABASE_URL,
    echo=os.getenv("SQL_ECHO","0")=="1",#默认关掉 SQL 日志，压测时日志本身会拖慢接口
    pool_size=10,#设置连接池中保持的持久连接数
    max_overflow=20,#设置连接池中最大连接数
    )
#创建异步会话工厂
AsyncSessionLocal=async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False, #表示提交后对象数据可用，不会重新查询数据库
    class_=AsyncSession
    )
#依赖项，用于获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
