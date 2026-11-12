"""生成用于索引/压测验证的测试新闻数据。

用法:
    python scripts/seed_news.py                  # 追加 10 万条
    python scripts/seed_news.py --count 200000   # 指定条数
    python scripts/seed_news.py --clean          # 先删除旧的 seed 数据再追加

清理:
    DELETE FROM news WHERE author = 'seed_bot';

用 author='seed_bot' 做标记，保证测试数据可一键删除，不影响原有 403 条真实数据。
"""

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import aiomysql

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from toutiao_backend.config.db_conf import ASYNC_DATABASE_URL

SEED_AUTHOR = "seed_bot"

NOUNS = ["经济", "科技", "体育", "娱乐", "教育", "健康", "汽车", "房产", "旅游", "美食"]
VERBS = ["发布", "宣布", "启动", "完成", "突破", "调整", "回升", "下滑", "落地", "获批"]
TAILS = ["最新进展", "市场观察", "深度解读", "现场直击", "数据盘点", "行业分析", "政策解读", "一线调查"]


def make_title(rng: random.Random, i: int) -> str:
    return f"{rng.choice(NOUNS)}{rng.choice(VERBS)}：{rng.choice(TAILS)}（{i}）"


def make_content(rng: random.Random) -> str:
    sentence = "记者在现场了解到，相关项目已经进入实施阶段，各方正在按照既定计划推进，后续进展将持续跟进。"
    return "\n".join(sentence * rng.randint(1, 3) for _ in range(rng.randint(3, 6)))


def build_rows(category_ids, count: int, rng: random.Random):
    now = datetime.now()
    rows = []
    for i in range(count):
        rows.append(
            (
                make_title(rng, i)[:255],
                f"这是第 {i} 条测试数据的简介，用于模拟真实新闻列表的长度。"[:500],
                make_content(rng),
                f"https://picsum.photos/seed/{i}/800/450"[:255],
                SEED_AUTHOR,
                rng.choice(category_ids),
                rng.randint(0, 50000),
                now - timedelta(seconds=rng.randint(0, 730 * 86400)),
            )
        )
    return rows


INSERT_SQL = (
    "INSERT INTO news (title, description, content, image, author, category_id, views, publish_time) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--batch", type=int, default=2_000)
    parser.add_argument("--clean", action="store_true", help="先删除 author='seed_bot' 的旧数据")
    args = parser.parse_args()

    rng = random.Random(20261108)  # 固定种子，保证多次生成数据分布一致，对比结果可复现
    u = urlparse(ASYNC_DATABASE_URL.replace("mysql+aiomysql://", "mysql://"))

    conn = await aiomysql.connect(
        host=u.hostname,
        port=u.port or 3306,
        user=u.username,
        password=u.password,
        db=u.path.lstrip("/"),
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        async with conn.cursor() as cur:
            if args.clean:
                await cur.execute("DELETE FROM news WHERE author=%s", (SEED_AUTHOR,))
                await conn.commit()
                print(f"已删除旧 seed 数据 {cur.rowcount} 条")

            await cur.execute("SELECT id FROM news_category ORDER BY id")
            category_ids = [r[0] for r in await cur.fetchall()]
            if not category_ids:
                raise SystemExit("news_category 为空，无法生成外键合法的数据")

            total = 0
            for offset in range(0, args.count, args.batch):
                n = min(args.batch, args.count - offset)
                rows = build_rows(category_ids, n, rng)
                await cur.executemany(INSERT_SQL, rows)
                await conn.commit()
                total += n
                print(f"已插入 {total}/{args.count}")

            await cur.execute("SELECT COUNT(*) FROM news")
            print(f"完成。news 总行数：{(await cur.fetchone())[0]}")
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
