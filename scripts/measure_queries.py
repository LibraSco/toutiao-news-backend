"""测量新闻接口关键 SQL 的执行计划与耗时，改造前后各跑一次做对比。

用法:
    python scripts/measure_queries.py

输出:
    每条 SQL 的 EXPLAIN（type / key / rows / Extra）+ 25 次执行的中位数与 P95。
"""

import asyncio
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import aiomysql

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from toutiao_backend.config.db_conf import ASYNC_DATABASE_URL

LIST_COLS = "id,title,description,image,author,category_id,views,publish_time"

# (名称, SQL, 参数构造器)  参数构造器接收 {"cid","nid","cursor"}，返回 SQL 参数元组
QUERIES = [
    ("列表-当前(无排序)", f"SELECT {LIST_COLS} FROM news WHERE category_id=%s LIMIT 10", lambda c: (c["cid"],)),
    ("列表-按时间倒序", f"SELECT {LIST_COLS} FROM news WHERE category_id=%s ORDER BY publish_time DESC, id DESC LIMIT 10", lambda c: (c["cid"],)),
    ("列表-计数", "SELECT COUNT(*) FROM news WHERE category_id=%s", lambda c: (c["cid"],)),
    ("相关推荐", f"SELECT {LIST_COLS} FROM news WHERE id<>%s AND category_id=%s ORDER BY publish_time DESC, views DESC LIMIT 5", lambda c: (c["nid"], c["cid"])),
    ("深分页-offset8000", f"SELECT {LIST_COLS} FROM news WHERE category_id=%s ORDER BY publish_time DESC, id DESC LIMIT 10 OFFSET 8000", lambda c: (c["cid"],)),
    ("深分页-游标", f"SELECT {LIST_COLS} FROM news WHERE category_id=%s AND (publish_time<%s OR (publish_time=%s AND id<%s)) ORDER BY publish_time DESC, id DESC LIMIT 10", lambda c: (c["cid"], c["cursor"][0], c["cursor"][0], c["cursor"][1])),
]

ROUNDS = 25


async def main() -> None:
    u = urlparse(ASYNC_DATABASE_URL.replace("mysql+aiomysql://", "mysql://"))
    conn = await aiomysql.connect(
        host=u.hostname, port=u.port or 3306, user=u.username,
        password=u.password, db=u.path.lstrip("/"), charset="utf8mb4",
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT category_id FROM news GROUP BY category_id ORDER BY COUNT(*) DESC LIMIT 1"
            )
            cid = (await cur.fetchone())[0]
            await cur.execute("SELECT id FROM news WHERE category_id=%s LIMIT 1", (cid,))
            nid = (await cur.fetchone())[0]

            # 取分类内第 8000 条附近的 (publish_time, id) 作为游标锚点，与 offset 8000 对位可比
            await cur.execute(
                "SELECT publish_time, id FROM news WHERE category_id=%s "
                "ORDER BY publish_time DESC, id DESC LIMIT 1 OFFSET 8000",
                (cid,),
            )
            cursor = await cur.fetchone()
            ctx = {"cid": cid, "nid": nid, "cursor": cursor}

            for name, sql, build_params in QUERIES:
                params = build_params(ctx)

                await cur.execute("EXPLAIN " + sql, params)
                cols = [d[0] for d in cur.description]
                row = dict(zip(cols, await cur.fetchone()))

                for _ in range(3):  # 预热，排除首次连接/解析的干扰
                    await cur.execute(sql, params)
                    await cur.fetchall()

                costs = []
                for _ in range(ROUNDS):
                    t0 = time.perf_counter()
                    await cur.execute(sql, params)
                    await cur.fetchall()
                    costs.append((time.perf_counter() - t0) * 1000)

                p50 = statistics.median(costs)
                p95 = sorted(costs)[max(0, int(len(costs) * 0.95) - 1)]
                print(
                    f"\n== {name}\n"
                    f"   type={row.get('type')} key={row.get('key')} rows={row.get('rows')} "
                    f"Extra={row.get('Extra')}\n"
                    f"   p50={p50:.2f}ms p95={p95:.2f}ms (n={ROUNDS})"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
