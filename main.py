import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from toutiao_backend.routers.news import router
from toutiao_backend.routers.users import users_router
from toutiao_backend.routers.history import history_router
from toutiao_backend.utils.exception_handlers import register_exception_handlers
from toutiao_backend.routers.favourite import favorite_router
from toutiao_backend.cache.news_cache import flush_news_views
from toutiao_backend.config.cache_conf import redis_client
from toutiao_backend.config.db_conf import AsyncSessionLocal

from fastapi.middleware.cors import CORSMiddleware

VIEWS_FLUSH_INTERVAL=10  #浏览量在 Redis 里先累加，每 10 秒落一次库

async def _flush_views_loop():
    while True:
        await asyncio.sleep(VIEWS_FLUSH_INTERVAL)
        try:
            async with AsyncSessionLocal() as session:
                await flush_news_views(session)
        except Exception as e:
            print(f"浏览量落库失败:{e}")

@asynccontextmanager
async def lifespan(app:FastAPI):
    task=asyncio.create_task(_flush_views_loop())
    yield
    task.cancel()
    await redis_client.aclose()

#允许所有来源的请求
app=FastAPI(lifespan=lifespan)
# 注册全局异常处理器
register_exception_handlers(app)
#添加中间件,解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],#允许的来源，开发阶段建议使用*，生产阶段建议指定具体的来源
    #allow_credentials 不能和 allow_origins=["*"] 同时开：浏览器会直接拒绝这种响应
    allow_credentials=False,
    allow_methods=["*"],#允许的请求方法
    allow_headers=["*"],#允许的请求头
)

@app.get("/")
async def root():
    return {"message":"Hello World"}


#挂载路由/注册路由
app.include_router(router)
app.include_router(users_router)
app.include_router(favorite_router)
app.include_router(history_router)







