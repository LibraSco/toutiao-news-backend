"""Locust 压测：列表首屏、详情、游标深页三种请求混跑。

先启动服务（关掉 SQL 日志）：
    SQL_ECHO=0 python -m uvicorn main:app --port 8013

再跑压测：
    locust -f scripts/locustfile.py --headless -u 50 -r 10 -t 30s --host http://127.0.0.1:8013

--csv 参数可以把结果落成 csv，方便和改造前的数字对比。
"""

import os
import random

from locust import HttpUser, between, task

# 改造前没有游标，对照测时用 DEEP_MODE=offset 走页码翻页
DEEP_MODE = os.getenv("DEEP_MODE", "cursor")


class NewsUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self):
        # 预热拿一批真实 id + 一个深页游标，避免压测里大量 404（空值缓存会掩盖真实耗时）
        # pageSize 必须和页码配套：800 页 * 10 条 = offset 8000，第 801 页才是非空数据
        r = self.client.get(
            "/api/news/list",
            params={"categoryId": 1, "page": 801, "pageSize": 10},
            name="warmup",
        )
        if r.status_code == 200:
            data = r.json()["data"]
            self.news_ids = [item["id"] for item in data["list"]]
            #改造前没有游标字段，get 拿不到就当没有
            self.cursor = data.get("nextCursor")
        else:
            self.news_ids = []
            self.cursor = None

    @task(10)
    def list_first_page(self):
        self.client.get(
            "/api/news/list",
            params={"categoryId": random.randint(1, 8), "pageSize": 10},
            name="list-first",
        )

    @task(4)
    def news_detail(self):
        if not self.news_ids:
            return
        self.client.get(
            "/api/news/detail",
            params={"id": random.choice(self.news_ids)},
            name="news-detail",
        )

    @task(2)
    def list_deep_cursor(self):
        if DEEP_MODE == "offset":
            self.client.get(
                "/api/news/list",
                params={"categoryId": 1, "page": 801, "pageSize": 10},
                name="list-offset-deep",
            )
            return
        if not self.cursor:
            return
        self.client.get(
            "/api/news/list",
            params={
                "categoryId": 1,
                "pageSize": 10,
                "lastPublishTime": self.cursor["publishTime"],
                "lastId": self.cursor["id"],
            },
            name="list-cursor-deep",
        )
