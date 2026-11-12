# fastapi-docs-rag
# 头条新闻后端

FastAPI + MySQL + Redis 的新闻资讯后端，包含分类、列表、详情、相关推荐、收藏、浏览历史、用户注册登录。

项目的重点不是"接口能跑"，而是把每个优化都做成**可复现、有数字、能讲清边界**的工程改动：联合索引消除 filesort、keyset 游标分页、缓存穿透/击穿/雪崩、浏览量写热点改造、缓存一致性、容器化与自动化测试。

## 技术栈

FastAPI / SQLAlchemy 2.0（异步）/ aiomysql / MySQL 8 / Redis 7 / Docker Compose / pytest / Locust

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/news/categories` | 新闻分类 |
| GET | `/api/news/list` | 新闻列表，支持游标分页（`lastPublishTime` + `lastId`），兼容老的 `page` 参数 |
| GET | `/api/news/detail` | 新闻详情 + 相关推荐，浏览量每次 +1 |
| PATCH | `/api/news/update` | 更新新闻，需登录；更新后详情缓存与列表缓存立即失效 |
| POST | `/api/user/register` `/api/user/login` | 注册 / 登录，返回 token |
| GET/PUT | `/api/user/info` `/api/user/update` `/api/user/password` | 用户信息 |
| POST/DELETE/GET | `/api/favorite/*` | 收藏 |
| POST/DELETE/GET | `/api/history/*` | 浏览历史 |

## 性能改造与实测

压测条件：本机 50 并发、持续 30 秒、单 uvicorn 进程、两边关闭 SQL 日志。改造前的数据用 `git archive` 拉出改造前的代码单独部署后测量，不是估算值。

| 场景 | 改造前 P95 | 改造后 P95 |
|---|---|---|
| 列表首屏 | 110 ms | 15 ms |
| 深分页（第 801 页） | 160 ms | 16 ms |
| 详情 | 240 ms | 26 ms |
| 整体 QPS | 256.79 req/s | 340.46 req/s（错误率 0） |

SQL 层（`scripts/measure_queries.py`，25 次执行取 P95）：

| 查询 | 改造前 | 改造后 |
|---|---|---|
| 相关推荐 | 499 ms（filesort，扫 43,896 行） | 0.98 ms（联合索引 + Using index condition） |
| 深分页 offset 8000 | 601 ms | 41.88 ms（加索引后）/ 2.18 ms（换游标后） |

### 1. 联合索引消除 filesort

列表、相关推荐、深分页都在按 `(category_id, publish_time DESC)` 过滤和排序。把这两个字段（以及 `id` 兜底）放进同一条联合索引后，MySQL 可以直接按索引顺序读，不再把结果查出来再排序。

索引：`idx_news_category_publish_views (category_id, publish_time DESC, views DESC)` 与 `idx_news_category_publish_id (category_id, publish_time DESC, id DESC)`。

### 2. keyset 游标分页

`LIMIT 10 OFFSET 8000` 的本质是"数过 8000 行再丢掉"，页越深越慢。改成上一页最后一条的 `(publish_time, id)` 作为游标，从它后面继续读，成本与页深无关。

- 排序加 `id DESC` 兜底，避免同一秒发布的数据重漏。
- 比较条件写成 `publish_time < ? OR (publish_time = ? AND id < ?)`。写成 `(a,b) < (x,y)` 行构造器时，优化器在这条降序索引上会退化成 ref 全扫，实测 40ms vs 1ms。
- `hasmore` 用"多取一条"判断，COUNT 只在首屏执行。

### 3. Redis 缓存

- **穿透**：不存在的数据缓存 `__NULL__` 30 秒。
- **击穿**：详情回源加 `SET NX` 互斥锁，其余请求轮询等待，40 并发实测只打 1 次数据库。
- **雪崩**：所有 TTL 加 20% 随机抖动。
- Redis 连接超时 0.5 秒，不可用时自动回落 MySQL，接口不报错。

### 4. 浏览量写热点

原来每次看详情都 `UPDATE news SET views = views + 1`，同一行被反复更新。现在改为 Redis `INCR`，每 10 秒把**绝对值**落库：重复执行结果一致，多进程同时写也不会多算。代价是最多丢 10 秒计数。

### 5. 缓存一致性

- 写路径：更新数据库 → 删除详情缓存 → 500ms 后延迟再删一次（清掉读请求可能回填的旧值）→ 列表版本号 +1。
- 列表缓存 key 形如 `news:list:{version}:{category}:{size}:{anchor}`，写一次只改一个版本号，整类立即失效，不用 `SCAN` 找 key。
- 只更新请求里传了的字段，`null` 视为不修改，避免把 `NOT NULL` 列写成空。

## 快速开始

### 方式一：Docker Compose

```bash
cp .env.example .env      # 按需修改 MYSQL_ROOT_PASSWORD
docker compose up -d --build
```

启动后访问 `http://localhost:8000/docs`。首次启动会自动建表并初始化分类；需要测试数据时：

```bash
docker compose exec app python scripts/seed_news.py --count 100000
```

如果拉取基础镜像失败，可先配置镜像加速，或从国内镜像拉取后重新打 tag。

### 方式二：本机运行

需要 Python 3.10+、MySQL 8、Redis 7。

```bash
pip install -r requirements.txt
cp .env.example .env      # 填 DATABASE_URL / REDIS_URL
python -m uvicorn main:app --port 8000
```

`DATABASE_URL` 示例：`mysql+aiomysql://root:password@127.0.0.1:3306/news_app`。

## 测试与压测

```bash
pytest -q                              # 17 个接口测试
python scripts/measure_queries.py      # EXPLAIN + P50/P95
locust -f scripts/locustfile.py --headless -u 50 -r 10 -t 30s --host http://127.0.0.1:8000
```

`DEEP_MODE=offset` 可让压测脚本走改造前的页码翻页，用于对照。

## 目录结构

```
main.py                     应用入口、生命周期、浏览量落库任务
toutiao_backend/
  config/                   数据库、Redis 连接
  models/                   ORM 模型
  schemas/                  请求/响应模型
  crud/                     数据库操作
  cache/                    缓存 key、空值缓存、互斥锁、浏览量计数
  routers/                  路由
  utils/                    鉴权、异常处理、统一响应
scripts/
  seed_news.py              造测试数据
  measure_queries.py        SQL 执行计划与耗时
  locustfile.py             压测脚本
  init_db.sql               容器首次启动建表
  migrations/               索引迁移
tests/                      接口与一致性测试
reports/                    压测结果 CSV
```

## 已知限制

- 更新接口只校验登录，没有管理员角色；生产环境需要补角色校验。
- 列表缓存按版本号整体失效，粒度较粗；写多读多时可细化到按分类维护版本号。
- 浏览量是最终一致，Redis 异常时最多丢 10 秒计数；Redis 未开持久化时重启会回到库里的值。
- 没有删除新闻的接口：收藏、历史、相关推荐都有外键引用，需要先确定级联策略。
- 压测是单机单进程数据，只用于验证优化效果，不代表生产容量。
