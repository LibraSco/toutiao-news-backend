import json
import os
import random
from typing import Any

import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()
#优先读环境变量，Docker Compose 里改成 redis://redis:6379/0 即可
#写 127.0.0.1 不写 localhost：Windows 上 localhost 会先解析成 IPv6，连不上只监听 IPv4 的 Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
#创建redis的连接对象
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=0.5,        #超时快速失败，Redis 挂了就回落到 MySQL，不让接口卡住
    socket_connect_timeout=0.5,
)

def jitter_ttl(expire: int, ratio: float = 0.2) -> int:
    """过期时间加随机抖动：大批 key 同一秒失效会把请求全打到数据库，这就是缓存雪崩"""
    return expire + random.randint(0, max(1, int(expire * ratio)))

#读取字符串
async def get_str(key):
    try:
        return await redis_client.get(key)
    except Exception as e:
        print(f"读取缓存失败:{e}")
        return None

#读取列表或字典
async def get_list_dict(key):
    raw = await get_str(key)
    if not raw:
        return None
    try:
        return json.loads(raw) #反序列化
    except json.JSONDecodeError:
        return None

#设置缓存
async def set_str(key, value:Any, expire:int=3600):
    try:
        if isinstance(value,(list,dict)):
            value=json.dumps(value,ensure_ascii=False) #序列化,保留中文
        await redis_client.set(key, value, ex=jitter_ttl(expire))
        return True
    except Exception as e:
        print(f"设置缓存失败:{e}")
        return False
