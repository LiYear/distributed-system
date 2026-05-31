# Python 微服务+分布式实战项目（全流程落地版）

## 项目整体规划

### 一、项目定位 & 技术栈

**项目名称**：极简电商微服务系统（用户服务、商品服务、订单服务、网关服务）

**架构模式**：**网关 + 多微服务 + 注册发现 + 消息队列 + 数据库分库**（标准分布式微服务架构）

**Python 核心技术栈**

1. Web 框架：**FastAPI**（高性能、异步、接口自动文档，Python 微服务首选）
2. 服务注册/发现/配置中心：**Nacos**（轻量、易部署，国内主流）
3. 网关：**FastAPI-Gateway**（基于 FastAPI 实现的轻量网关，含鉴权/限流/熔断/监控/CORS）
4. 消息队列（分布式解耦、异步通信）：**RabbitMQ**（订单异步通知、流量削峰 + 本地消息表模式）
5. 数据库：**MySQL 8.0**（分库：用户库、商品库、订单库）
6. ORM：**SQLAlchemy 2.0（异步）**
7. 缓存（分布式缓存）：**Redis**（热点商品缓存 + 缓存穿透/击穿/雪崩防护）
8. 服务通信：**HTTP 接口调用（统一 httpx）+ 异步 MQ**
9. 认证 & 安全：**JWT Token 鉴权 + bcrypt 密码哈希**
10. 配置管理：**python-dotenv + .env 环境变量（统一配置模块 + 启动校验）**
11. 容器化（统一部署）：**Docker + Docker Compose（基础设施 + 应用层分离编排）**
12. 全局异常处理：统一响应格式 + TraceID + BizException
13. 接口文档：自动生成 Swagger / ReDoc

### 二、业务模块拆分（标准微服务拆分）

| 服务名称 | 端口 | 职责 | 数据库 |
| ---- | ---- | ---- | ---- |
| Gateway 网关服务 | 8000 | 统一入口、动态路由、JWT鉴权、限流、熔断、CORS、日志监控 | 无 |
| User-Service 用户服务 | 8001 | 注册、登录、用户信息 | `db_user` |
| Goods-Service 商品服务 | 8002 | 商品CRUD、商品列表、库存、Redis缓存 | `db_goods` |
| Order-Service 订单服务 | 8003 | 下单（幂等）、订单查询、本地消息表(增强版)投递MQ、死信管理Admin API | `db_order` |

**业务流程**：
客户端 → 网关(8000) → 对应微服务
1. 用户注册/登录 → 用户服务（bcrypt 密码哈希 + JWT 签发）
2. 浏览商品 → 商品服务（Redis 多级缓存防护）
3. 提交订单 → 订单服务（幂等校验 → 扣库存 → 本地消息表增强版 → MQ 异步推送 + 死信管理）

---

## 前置环境准备（必做，一步一步落地）

> 全程基于 **Windows / Linux / Mac** 通用，优先使用 Docker 一键部署中间件，避免环境踩坑

### 步骤1：安装基础软件

1. 安装 Python 3.10+（推荐 3.11），配置环境变量
2. 安装 **Docker + Docker Compose**（所有中间件统一容器部署，不用本地装）
   - Windows/Mac：直接装 Docker Desktop
   - Linux：按官方教程安装 Docker & Compose
3. 代码编辑器：VS Code / PyCharm

### 步骤2：编写 Docker Compose 启动所有中间件

项目分两层编排：
- `micro-service-env/docker-compose.yml` — 基础设施（MySQL / Redis / RabbitMQ / Nacos）
- `python-micro-service/docker-compose.yml` — 应用层（4个微服务 + MQ消费者）

先启动基础设施。完整内容见：

📄 `micro-service-env/docker-compose.yml` **第1-55行**

#### 启动中间件（终端执行）

进入 `micro-service-env` 目录，执行：

```bash
docker-compose up -d
```

等待 1~2 分钟，所有容器启动完成。MySQL 启动时会**自动创建** `db_user`、`db_goods`、`db_order` 三个库，无需手动执行 SQL。

#### 验证中间件是否正常（逐个检查）

1. **Nacos 注册中心** — 浏览器访问：`http://localhost:8848/nacos`，账号密码：`nacos / nacos` → 登录成功即为正常。
2. **RabbitMQ 管理后台** — 访问：`http://localhost:15672`，账号：`admin` 密码：`admin123` → 登录成功。
3. **Redis**：默认端口 6379，无需页面，后续代码连接测试。
4. **MySQL**：端口 **13306**，账号 `root` 密码 `123456`。

---

## 项目整体目录结构

```
python-micro-service/
├── config.py                       # 统一配置模块（所有服务共用，从 .env 读取）
├── .env.example                    # 环境变量模板（复制为 .env 填入实际值）
├── .gitignore                      # Git 忽略规则（保护 .env 不提交）
├── exceptions.py                   # 统一异常处理（ResponseModel / BizException / TraceID）
├── requirements.txt                # 合并依赖文件（所有服务共用）
├── Dockerfile                      # 通用 Docker 镜像（4个微服务共用）
├── docker-compose.yml              # 应用层编排（4微服务 + MQ消费者）
├── GAP-ANALYSIS.md                 # 项目 vs 企业级差距分析
├── LEARNING-ROADMAP.md             # 学习路线图
│
├── gateway/                        # 网关服务 (8000)
│   └── main.py                     # 增强版（鉴权/限流/熔断/CORS/监控/Docker服务发现）
│
├── user-service/                   # 用户服务 (8001)
│   ├── main.py                     # 注册 + 登录（bcrypt 密码哈希 + JWT 签发 + CORS + 全局异常）
│   ├── database.py                 # MySQL 连接（从统一配置读取）
│   ├── models.py
│   ├── schemas.py                  # 含 Field 校验 + UserLogin / LoginResponse
│   └── utils/
│       ├── __init__.py
│       └── password.py             # bcrypt 密码哈希 & 校验工具
│
├── goods-service/                  # 商品服务 (8002)
│   ├── main.py                     # Redis 多级缓存（穿透/击穿/雪崩防护）+ CORS
│   ├── database.py
│   ├── models.py
│   └── schemas.py                  # 含 Field 校验
│
├── order-service/                  # 订单服务 (8003)
│   ├── main.py                     # 幂等下单 + 本地消息表(增强版) + MQ 发送 + 死信Admin API + CORS
│   ├── database.py
│   ├── models.py                   # Order + OutboxMessage（增强：message_id/schema_version/next_retry_at/索引）
│   ├── schemas.py                  # 含 Field 校验 + idempotency_key
│   └── mq_consumer.py              # RabbitMQ 消费者（凭据从环境变量读取）
│
└── README.md
```

---

## 第一部分：公共依赖 & 统一配置

### 通用依赖清单（顶层 `requirements.txt`，所有服务共用）

📄 `python-micro-service/requirements.txt` **第1-38行**

**安装依赖**：在 `python-micro-service` 根目录执行：

```bash
pip install -r requirements.txt
```

### 步骤3.5：配置环境变量（首次运行必须）

项目采用 **统一环境变量管理**，所有敏感信息（数据库密码、JWT密钥、MQ凭据等）不再硬编码。

```bash
# 1. 复制模板
cp .env.example .env

# 2. 编辑 .env，填入实际值（至少修改以下几项）
#    JWT_SECRET=your-random-secret-key-at-least-32-chars   ← 必须改！
#    DB_PASSWORD=your_mysql_password
#    RABBITMQ_PASSWORD=your_rabbitmq_password
```

> **核心机制**：`config.py` 是所有服务共享的统一配置模块，启动时自动：
> - 加载 `.env` 文件（通过 `python-dotenv`）
> - 校验必填项（如 `JWT_SECRET` 为空则拒绝启动并提示错误）
>
> 各服务的 `database.py`、`main.py` 均从 `config.py` 导入配置，源码中不再出现任何密码或硬编码连接串。

### 环境变量配置项说明

📄 `python-micro-service/.env` **第1-49行**

### 统一异常处理模块（exceptions.py）

项目新增了 `exceptions.py`，所有微服务共享使用，提供：

1. **`ResponseModel`** — 统一 API 响应格式（`success()` / `error()`），含 `code` / `message` / `data` / `trace_id` / `timestamp`
2. **`BizException`** — 自定义业务异常，可设置 `code` 和 `message`
3. **TraceID** — 请求追踪标识，便于全链路排查
4. **`register_exception_handlers(app)`** — 一键注册全局异常处理器，捕获三类异常：
   - `BizException` → 返回自定义业务错误（HTTP 200 + body.code 区分）
   - `RequestValidationError` → 返回 422 + 字段级错误详情
   - `Exception` → 返回 500 + 隐藏堆栈（仅日志记录）

各服务在 `main.py` 中统一调用 `register_exception_handlers(app)` 即可启用。

---

## 第二部分：逐个开发微服务（从底层到上层）

### 一、开发【User-Service 用户服务】端口 8001

#### 1. user-service/database.py 异步数据库连接（环境变量化）

📄 `user-service/database.py` **第1-22行**

#### 2. user-service/models.py 数据库模型

📄 `user-service/models.py` **第1-12行**

#### 3. user-service/schemas.py 数据校验模型（带 Field 约束）

📄 `user-service/schemas.py` **第1-28行**

#### 4. user-service/main.py 主服务（含 CORS + 全局异常 + 健康检查）

📄 `user-service/main.py` **第1-112行**

#### 新增文件 `user-service/utils/password.py`（bcrypt 密码工具）：

📄 `user-service/utils/password.py` **第1-20行**

#### 启动用户服务

```bash
cd user-service && python main.py
```

文档地址：`http://127.0.0.1:8001/docs`，Nacos 服务列表出现 `user-service` 即为正常。

---

### 二、开发【Goods-Service 商品服务】端口 8002（含 Redis 多级缓存防护）

#### 1. goods-service/database.py

📄 `goods-service/database.py` **第1-21行**

#### 2. goods-service/models.py

📄 `goods-service/models.py` **第1-12行**

#### 3. goods-service/schemas.py（带 Field 约束）

📄 `goods-service/schemas.py` **第1-18行**

#### 4. goods-service/main.py（含 CORS + 缓存穿透/击穿/雪崩防护 + Cache-Aside 延迟双删）

核心缓存策略升级：
- **缓存穿透防护**：缓存空值标记（`_empty`），短 TTL 60 秒
- **缓存击穿防护**：分布式锁（`SET NX EX`），抢锁查 DB，未抢到则等待重试
- **缓存雪崩防护**：TTL 随机抖动 300~360 秒
- **写路径**：写 DB 后删除缓存（Cache-Aside 延迟双删）

📄 `goods-service/main.py` **第1-148行**

#### 启动商品服务

```bash
cd goods-service && python main.py
```

Nacos 服务列表出现 `goods-service` 即为正常，文档地址：`http://127.0.0.1:8002/docs`

---

### 三、开发【Order-Service 订单服务】端口 8003（幂等 + 本地消息表增强版 + MQ 异步 + 死信管理）

订单服务核心升级：
- **幂等性**：`idempotency_key` 唯一索引 → 防止重复下单
- **本地消息表（Outbox Pattern 增强版）**：订单 + 消息在同一 DB 事务中写入 → 后台异步投递 MQ → 保证最终一致性
  - `message_id` (UUID)：消息唯一标识，Consumer 可做幂等消费
  - `schema_version`：消息体版本号，格式变更时兼容处理
  - 指数退避重试：10s → 20s → 40s，避免重试风暴
  - 分批提交：减少 DB IO 往返
  - 联合唯一索引 + 复合索引加速查询
- **死信管理 Admin API**：查询/重试 failed 消息 + 统计面板
- **CORS + 全局异常 + 健康检查**：与其他服务一致

#### 1. order-service/database.py

📄 `order-service/database.py` **第1-21行**

#### 2. order-service/models.py（含本地消息表）

📄 `order-service/models.py` **第1-37行**

#### 3. order-service/schemas.py（含 idempotency_key）

📄 `order-service/schemas.py` **第1-25行**

#### 4. order-service/mq_consumer.py（RabbitMQ 消费者）

📄 `order-service/mq_consumer.py` **第1-28行**

#### 5. order-service/main.py（下单接口：幂等 + 本地消息表 + 事务保护）

📄 `order-service/main.py` **第1-330行**

> **核心变化**：
> - `idempotency_key` 幂等键 + 唯一索引 → 防止重复下单
> - **本地消息表增强版（Outbox Pattern v2）** → 订单和消息在同一 DB 事务中写入，后台异步扫描投递到 MQ
>   - `message_id` (UUID) → 消息唯一标识，Consumer 可做幂等消费
>   - `schema_version` "1.0" → 消息体版本号，格式变更兼容
>   - 指数退避重试(10s/20s/40s)，分批 commit，复合索引加速
>   - 联合唯一索引 `(topic, message_id)` 防重复写入
> - **死信管理 Admin API**（3 个接口）：
>   - `GET /admin/outbox/dead-letters` — 查看 failed/pending 消息列表
>   - `POST /admin/outbox/{message_id}/retry` — 手动重试失败消息
>   - `GET /admin/outbox/stats` — outbox 统计概览（pending/sent/failed 数量）
> - 商品服务地址通过 `GOODS_SERVICE_HOST` 环境变量配置（Docker 容器间用服务名通信）
> - 下单失败时自动 `rollback`，防止脏数据

#### 启动订单服务 & MQ 消费者

1. 启动订单服务：`cd order-service && python main.py`
2. 新开终端，启动消费者：`python mq_consumer.py`

Nacos 出现 `order-service` 即为正常。

---

## 第三部分：开发【Gateway 网关服务】端口 8000

网关作用：**统一入口、动态路由转发、JWT鉴权、IP限流、熔断降级、CORS、请求日志监控**

### gateway/main.py 增强版 — 核心变化

完整代码见 `gateway/main.py`，关键特性：

- 全部配置从 `.env` 环境变量读取（`config.py` + `validate_config`）
- JWT 鉴权白名单（`/user/register`、`/user/login`、`/health`、`/docs`、`/openapi.json`）
- **CORS 跨域中间件**（从 `CORS_ORIGINS` 配置读取允许来源）
- **统一异常处理**（`register_exception_handlers`）
- **Docker 容器间服务发现**：Nacos 返回 `0.0.0.0` 时自动回退到 Docker Compose 服务名
- 路由转发时传递 query string
- 健康检查 `/health` + 网关指标 `/metrics/gateway`（含熔断状态、限流统计）
- 启动时通过 `@app.on_event("startup")` 注册到 Nacos

#### 核心模块一览

**配置导入 + CORS + 异常处理 + Nacos 服务发现**：

📄 `gateway/main.py` **第14-129行**（配置导入、CORS 中间件、全局异常、ServiceDiscovery 类、Nacos 注册函数）

**JWT 鉴权白名单 + 限流器 + 熔断器 + Token 创建**：

📄 `gateway/main.py` **第44-234行**（AuthMiddleware 鉴权类、RateLimiter 限流器、CircuitBreaker 熔断器）

**统一路由转发（含 query string + 熔断联动）**：

📄 `gateway/main.py` **第255-312行**（gateway_route 函数：限流→路由匹配→服务发现→熔断检查→HTTP转发→响应返回）

**监控接口 + 启动入口**：

📄 `gateway/main.py` **第238-251行**（`/metrics/gateway` 接口）及 **第317-325行**（startup 事件 + `__main__` 入口）

#### 启动网关

```bash
cd gateway && python main.py
```

网关文档地址：`http://127.0.0.1:8000/docs`
- `/health` — 健康检查
- `/metrics/gateway` — 网关运行指标（熔断状态、服务缓存、限流统计）

---

## 第四部分：Docker Compose 一键部署

项目支持两层 Docker Compose 编排，实现全栈容器化部署。

### 应用层 `docker-compose.yml`（python-micro-service/）

📄 `python-micro-service/docker-compose.yml` **第1-127行**

### 部署流程

```bash
# 1. 启动基础设施
cd micro-service-env && docker-compose up -d

# 2. 启动微服务
cd python-micro-service && docker-compose up -d

# 3. 验证
curl http://localhost:8080/health
```

---

## 第五部分：全流程联调测试

### 所有服务启动清单（本地开发模式）

0. **配置环境变量**：`cp .env.example .env` 并填入实际值（首次必须）
1. 中间件：`cd micro-service-env && docker-compose up -d`（MySQL/Redis/RabbitMQ/Nacos）
2. 用户服务：`cd user-service && python main.py` (8001)
3. 商品服务：`cd goods-service && python main.py` (8002)
4. 订单服务：`cd order-service && python main.py` (8003)
5. MQ 消费者：`cd order-service && python mq_consumer.py`
6. 网关服务：`cd gateway && python main.py` (8000)

### 测试步骤（全部访问网关 8000，不直连子服务）

网关文档地址：`http://127.0.0.1:8000/docs`

增强版网关启用了 JWT 鉴权，除白名单接口（`/user/register`、`/user/login`、`/health`）外，其他接口需携带 Token 访问。

#### 1. 注册用户（密码 bcrypt 哈希存储）

- 接口：`POST /user/register`（**无需鉴权**，已在白名单）
- 请求体：

```json
{"username":"test01","password":"123456","phone":"13800138000"}
```

- 数据库中存储的是 `$2b$12$N9qo8uLOickG...` 格式的 **bcrypt 哈希**，不再是明文

#### 2. 用户登录（密码校验 + 获取 JWT）

- 接口：`POST /user/login`（**无需鉴权**，已在白名单）
- 请求体：

```json
{"username":"test01","password":"123456"}
```

- 响应示例：

```json
{
  "user_id": 1,
  "username": "test01",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

后续请求在 **Headers** 中添加 `Authorization: Bearer <token>` 即可。

#### 3. 添加商品

- 接口：`POST /goods/add`（**需鉴权**）
- Headers：`Authorization: Bearer <token>`
- 请求体：

```json
{"name":"Python实战书籍","price":59.9,"stock":100}
```

- 写 DB 后自动删除 Redis 缓存（Cache-Aside 延迟双删）

#### 4. 创建订单（核心流程：幂等 + 本地消息表增强版）

- 接口：`POST /order/create`（**需鉴权**）
- Headers：`Authorization: Bearer <token>`
- 请求体（注意 `idempotency_key` 必填，防止重复下单）：

```json
{"user_id":1,"goods_id":1,"buy_num":2,"idempotency_key":"order_20260531_u1_g1"}
```

**现象**：
1. 幂等检查：相同 `idempotency_key` 不会重复创建订单
2. 商品库存自动扣减 2（通过 httpx 统一调用商品服务）
3. 订单 + 消息在同一 DB 事务中写入（原子性保证，含 `message_id` + `schema_version`）
4. 后台 `outbox_relay_loop` 增强版定时扫描：指数退避(10s/20s/40s) + 分批提交 + 复合索引加速查询
5. MQ 投递成功 → 消费者打印消息；投递失败 → 自动重试 → 超过 3 次 → 标记 failed
6. **死信管理**：访问 `GET /admin/outbox/dead-letters` 查看 failed 消息，`POST /admin/outbox/{message_id}/retry` 手动重试

#### 5. 查询订单 / 查询商品

直接调用网关对应接口即可（**需鉴权**）。

#### 6. 查看网关运行指标

```bash
curl http://127.0.0.1:8000/metrics/gateway
```

返回熔断器状态、服务缓存、限流统计等信息。

---

## 第六部分：架构知识点总结 & 进阶优化方向

### 已落地的分布式/微服务核心能力

1. **服务拆分**：按业务域垂直拆分，分库分表
2. **服务注册与发现**：Nacos 统一管理所有服务 + Docker 容器名回退
3. **API 网关**：统一入口、动态路由（Nacos 服务发现）、CORS 跨域
4. **JWT 鉴权认证**：Token 白名单机制，保护业务接口
5. **密码安全存储**：bcrypt 哈希（自动加盐），数据库泄露也无法还原明文
6. **统一环境变量管理**：`config.py` + `.env` + 启动校验，源码零密钥
7. **请求限流**：基于 IP 滑动窗口限流，防止刷接口
8. **熔断降级**：连续失败自动熔断，防止服务雪崩
9. **请求日志 & 监控**：全链路日志、耗时统计、运行指标接口
10. **分布式缓存**：Redis 缓存热点数据
11. **缓存穿透防护**：空值缓存（短 TTL）
12. **缓存击穿防护**：分布式锁（`SET NX EX`）
13. **缓存雪崩防护**：TTL 随机抖动
14. **异步解耦**：RabbitMQ 实现订单异步通知，削峰填谷
15. **本地消息表（Outbox Pattern v2）**：订单 + 消息写入同一 DB 事务（增强版：message_id/schema_version/指数退避/分批提交/SKIP LOCKED）
16. **幂等性设计**：`idempotency_key` 唯一索引，防止重复下单/重复消费
17. **死信管理 Admin API**：3 个接口查询/重试 failed 消息 + 统计面板
17. **Pydantic 数据校验**：Field 约束（长度/格式/范围/正则）+ 全局校验异常处理
18. **统一 HTTP 客户端**：全项目 httpx（替代混用的 aiohttp），连接池行为一致
19. **异步编程**：全链路 Python 异步（FastAPI + 异步ORM + 异步Redis/MQ）
20. **容器化部署**：Dockerfile + Docker Compose（基础设施 + 应用层分离编排）
21. **全局异常处理**：`ResponseModel` + `BizException` + TraceID 全链路追踪

### 进阶优化（后续可扩展）

1. 配置中心热更新：Nacos Config（当前为基础 `.env` + `config.py` 模式）
2. 链路追踪：OpenTelemetry + Jaeger / SkyWalking
3. 结构化 JSON 日志 + ELK / Loki 聚合
4. 分布式事务：Seata 解决跨库一致性问题（当前本地消息表已解决部分场景）
5. 测试覆盖：pytest 单元测试 + 集成测试
6. CI/CD 流水线：GitHub Actions / GitLab CI 自动化
7. Kubernetes 编排：K8s 部署替代 Docker Compose

---

## 常见问题排错

1. **服务启动失败提示 "配置不完整"**：检查 `.env` 文件是否创建，必填项（`JWT_SECRET`、`DB_PASSWORD`、`RABBITMQ_PASSWORD`）是否已填写
2. **Nacos 注册失败**：检查 8848 端口是否被占用，Docker 容器是否正常启动
3. **MySQL 连接失败**：确认 `.env` 中 `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD`/`DB_NAME_*` 是否正确（注意宿主机端口为 **13306**）
4. **Redis/RabbitMQ 连不上**：核对 `.env` 中的端口、账号密码
5. **服务之间调用 404**：检查路由地址、端口（`.env` 中的 `*_PORT`）是否正确
6. **MQ 收不到消息**：确认队列名一致，消费者正常监听，消息是否仍在 `outbox_messages` 表中 pending
7. **401 未提供认证 Token**：访问非白名单接口时需要在 Headers 中携带 `Authorization: Bearer <token>`，先通过 `/user/login` 获取
8. **重复下单**：检查 `idempotency_key` 是否唯一，同一幂等键只能创建一次订单
9. **消息投递失败重试**：`outbox_relay_loop` 采用指数退避(10s/20s/40s)，查看 `retry_count` 和 `next_retry_at` 字段判断重试状态
10. **死信处理**：访问 `GET /admin/outbox/dead-letters?status=failed` 查看失败消息，`POST /admin/outbox/{message_id}/retry` 手动重试

该项目是 Python 微服务分布式**入门到落地标准模板**，每一段代码均可直接运行，架构符合企业基础微服务规范（含安全加固 + 配置管理 + 缓存三防 + 幂等设计 + 本地消息表增强版 + 死信管理 + 容器化部署）。
