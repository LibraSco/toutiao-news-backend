#存放新闻相关的缓存方法
import asyncio
import json
import time
from datetime import datetime
from typing import Any,Dict,List,Optional,Tuple

from toutiao_backend.config.cache_conf import get_list_dict,get_str,redis_client,set_str
CATEGORY_KEY='news:categories'

#获取新闻分类缓存
async def get_news_categories():
    return await get_list_dict(CATEGORY_KEY)

#写入新闻分类缓存
async def set_news_categories(categories:List[Dict[str,Any]],expire:int=3600):
    return await set_str(CATEGORY_KEY,categories,expire)

NULL_MARK='__NULL__'   #空值占位：缓存里存的不是数据，而是"这条不存在"，用来防缓存穿透
LIST_EXPIRE=60         #列表变化快，缓存 1 分钟
DETAIL_EXPIRE=300      #详情体量大、变化慢，缓存 5 分钟
NULL_EXPIRE=30         #空值只缓存 30 秒，避免数据库里刚加的数据一直查不到

def news_to_dict(news) -> Dict[str,Any]:
    """把 ORM 对象转成和 FastAPI 默认序列化一致的字典（时间用 isoformat）"""
    data={}
    for column in news.__table__.columns:
        value=getattr(news,column.name)
        data[column.name]=value.isoformat() if isinstance(value,datetime) else value
    return data

#---- 列表缓存 ----
LIST_VERSION_KEY='news:list:version'

async def get_list_version() -> int:
    """列表缓存的版本号；Redis 不可用时返回 0，缓存读写本来也会失败，不影响正确性"""
    try:
        return int(await redis_client.get(LIST_VERSION_KEY) or 0)
    except Exception:
        return 0

async def bump_list_version() -> int:
    """新闻一改就自增版本号：所有列表 key 立刻失效，旧 key 靠 TTL 自然过期"""
    try:
        return await redis_client.incr(LIST_VERSION_KEY)
    except Exception:
        return 0

def list_key(category_id:int,page_size:int,anchor:str,version:int=0) -> str:
    return f'news:list:{version}:{category_id}:{page_size}:{anchor}'

async def get_news_list(category_id:int,page_size:int,anchor:str,version:int=0):
    return await get_list_dict(list_key(category_id,page_size,anchor,version))

async def set_news_list(category_id:int,page_size:int,anchor:str,data:Dict[str,Any],version:int=0):
    return await set_str(list_key(category_id,page_size,anchor,version),data,LIST_EXPIRE)

#---- 详情缓存 ----
def detail_key(news_id:int) -> str:
    return f'news:detail:{news_id}'

async def get_news_detail(news_id:int):
    """None=没缓存，False=缓存了"不存在"，dict=命中"""
    raw=await get_str(detail_key(news_id))
    if raw is None:
        return None
    if raw==NULL_MARK:
        return False
    return json.loads(raw)

async def set_news_detail(news_id:int,data:Dict[str,Any]):
    return await set_str(detail_key(news_id),data,DETAIL_EXPIRE)

async def set_news_null(news_id:int):
    return await set_str(detail_key(news_id),NULL_MARK,NULL_EXPIRE)

async def delete_news_detail(news_id:int):
    """写库之后删缓存，而不是更新缓存：删是幂等的，也不会把并发写的旧值盖回去"""
    try:
        await redis_client.delete(detail_key(news_id))
    except Exception as e:
        print(f"删除缓存失败:{e}")

async def delete_news_detail_later(news_id:int,delay:float=0.5):
    """延迟双删：读请求可能刚从库里读到旧值、正等着回填缓存，晚点再删一次把它清掉"""
    await asyncio.sleep(delay)
    await delete_news_detail(news_id)

#---- 重建互斥锁：热点 key 过期时只放一个请求回源，其余请求等结果，防缓存击穿 ----
LOCK_EXPIRE=5
_RELEASE_LUA="if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"

async def acquire_detail_lock(news_id:int) -> Optional[str]:
    token=str(time.time())
    try:
        ok=await redis_client.set(f'lock:news:detail:{news_id}',token,nx=True,ex=LOCK_EXPIRE)
    except Exception:
        return None  #Redis 不可用就不加锁，直接查库
    return token if ok else None

async def release_detail_lock(news_id:int,token:str):
    try:
        await redis_client.eval(_RELEASE_LUA,1,f'lock:news:detail:{news_id}',token)
    except Exception:
        pass

#---- 浏览量计数：先写 Redis 再定时落库，避免每次看详情都去 UPDATE 同一行 ----
VIEWS_EXPIRE=7*24*3600
VIEWS_PENDING='news:views:pending'

def views_key(news_id:int) -> str:
    return f'news:views:{news_id}'

async def init_news_views(news_id:int,views:int):
    """用数据库里的旧值兜底初始化，SET NX 保证并发只有一个请求写进基线"""
    try:
        await redis_client.set(views_key(news_id),views,nx=True,ex=VIEWS_EXPIRE)
    except Exception:
        pass

async def incr_news_views(news_id:int) -> Optional[int]:
    """返回自增后的浏览量；Redis 不可用返回 None，由调用方退回数据库自增"""
    try:
        views=await redis_client.incr(views_key(news_id))
        await redis_client.expire(views_key(news_id),VIEWS_EXPIRE)
        await redis_client.sadd(VIEWS_PENDING,news_id)
        return views
    except Exception:
        return None

async def flush_news_views(db) -> int:
    """把待落库的浏览量写回 MySQL。写的是绝对值，重复执行结果一样"""
    from toutiao_backend.crud.news import crud_set_news_views
    try:
        news_ids=await redis_client.smembers(VIEWS_PENDING)
    except Exception:
        return 0
    flushed=0
    for news_id in news_ids:
        raw=await get_str(views_key(int(news_id)))
        if raw is None:
            await redis_client.srem(VIEWS_PENDING,news_id)
            continue
        if await crud_set_news_views(db,int(news_id),int(raw)):
            await redis_client.srem(VIEWS_PENDING,news_id)
            flushed+=1
    return flushed
