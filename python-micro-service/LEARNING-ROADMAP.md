# 分布式微服务学习路线图

> 项目：极简电商微服务系统
> 目标：从零掌握分布式微服务架构及企业级规范
> 建议：按阶段循序渐进，每个阶段包含"理解概念 → 阅读代码 → 动手实践"

---

## 阶段 0：环境搭建 & 基础设施认知

**目标**：理解分布式系统需要的中间件，并能一键启动

| 顺序 | 学习内容 | 对应文件 | 要点 |
|------|---------|---------|------|
| 0.1 | 理解项目整体架构 | `README.md` § 一 | 画架构图：4个微服务 + 网关 + 4个中间件的关系 |
| 0.2 | 理解 Docker Compose 编排 | `micro-service-env/docker-compose.yml` | 4个中间件如何统一管理；端口映射、网络、数据卷 |
| 0.3 | 启动并验证每个中间件 | 按 README § 步骤2 操作 | Nacos 控制台、RabbitMQ 管理后台、MySQL 分库 |

**思考题**：
- 为什么用 Docker 而不是本地安装中间件？
- 每个中间件的角色是什么？（Nacos/Redis/RabbitMQ/MySQL）
- 为什么 MySQL 要分 3 个库而不是 1 个库？

---

## 阶段 1：配置管理 & 工程规范

**目标**：理解企业级配置管理方式——源码零密钥、统一配置、启动校验

| 顺序 | 学习内容 | 对应文件 | 要点 |
|------|---------|---------|------|
| 1.1 | 环境变量管理 | `.env.example` | 理解 `.env` vs `.env.example`，`.gitignore` 保护敏感信息 |
| 1.2 | 统一配置模块 | `config.py` | `python-dotenv` 加载 `.env`；`get_db_url()` 动态拼接连接串；`validate_config()` 启动必填校验 |
| 1.3 | 全局异常处理 | `exceptions.py` | 三层异常处理：业务异常 / Pydantic 校验 / 未预期异常；统一响应格式 `ResponseModel`；TraceID 生成 |

**思考题**：
- 为什么 `config.py` 要从 `.env` 读取而不是硬编码？
- `validate_config()` 的启动校验有什么好处？（对比静默使用默认值的风险）
- 异常处理器为什么要把堆栈隐藏，不返回给客户端？

---

## 阶段 2：单服务深入（自底向上）

**目标**：理解一个微服务从数据库到接口的完整链路

### 2.1 用户服务 (User-Service) — 最基础的服务

| 顺序 | 学习内容 | 对应文件 | 要点 |
|------|---------|---------|------|
| 2.1.1 | 异步数据库连接 | `user-service/database.py` | SQLAlchemy 2.0 异步引擎；`AsyncSessionLocal`；`get_db()` 依赖注入 |
| 2.1.2 | ORM 模型定义 | `user-service/models.py` | 继承 `Base`；`__tablename__`；字段类型 |
| 2.1.3 | Pydantic 数据校验 | `user-service/schemas.py` | `BaseModel`；`Field()` 约束；`from_attributes` 兼容 ORM |
| 2.1.4 | FastAPI 接口实现 | `user-service/main.py` | 路由定义；依赖注入 `Depends(get_db)`；`response_model` |
| 2.1.5 | bcrypt 密码哈希 | `user-service/utils/password.py` | `passlib` 自动加盐；为什么不能存明文 |
| 2.1.6 | JWT 签发 | `user-service/main.py` 登录接口 | Header.Payload.Signature 结构；过期时间 |

**动手**：启动 user-service，用 Swagger (`/docs`) 调注册和登录接口

### 2.2 商品服务 (Goods-Service) — 加 Redis 缓存

| 顺序 | 学习内容 | 对应文件 | 要点 |
|------|---------|---------|------|
| 2.2.1 | Redis 异步客户端 | `goods-service/main.py` | `aioredis.from_url()`；`startup/shutdown` 事件 |
| 2.2.2 | Cache-Aside 模式 | `goods-service/main.py` 查询接口 | 先查缓存 → 未命中查 DB → 回写缓存；TTL 过期策略 |
| 2.2.3 | 缓存的边界条件 | 思考 | 缓存穿透/击穿/雪崩分别是什么？本项目处理了吗？ |

**动手**：调两次查询同一商品，观察第2次是否更快（缓存命中）

### 2.3 订单服务 (Order-Service) — 服务间调用 + 本地消息表 + 死信管理

| 顺序 | 学习内容 | 对应文件 | 要点 |
|------|---------|---------|------|
| 2.3.1 | 服务间 HTTP 调用 | `order-service/main.py` `deduct_goods_stock()` | `httpx.AsyncClient`；同步调用 vs 异步调用的区别 |
| 2.3.2 | **本地消息表模式（Outbox Pattern）** | `order-service/models.py` `OutboxMessage` | 为什么不能在事务内直接发 MQ？订单+消息同一 DB 事务原子写入；最终一致性 vs 强一致性 |
| 2.3.3 | **Outbox 增强版字段设计** | `order-service/models.py` | `message_id`(UUID，Consumer 幂等消费用)；`schema_version`(消息体版本兼容)；`next_retry_at`(指数退避)；联合唯一索引防重复写入 |
| 2.3.4 | **后台投递逻辑（outbox_relay_loop）** | `order-service/main.py` `relay_pending_messages()` | 定时扫表 → 指数退避(10s/20s/40s) → 分批 commit → `SKIP LOCKED` 多实例安全 → failed 标记死信 |
| 2.3.5 | RabbitMQ 消息消费 & 幂等 | `order-service/mq_consumer.py` | `connect_robust` 自动重连；`async for message in queue`；手动 ACK；基于 `message_id` 去重 |
| 2.3.6 | **死信管理 Admin API** | `order-service/main.py` `/admin/outbox/*` | 查看失败消息、手动重试、统计面板——生产环境运维必备 |

**动手**：
1. 启动 order-service（自动启动 outbox_relay_loop 后台任务），同时启动 mq_consumer
2. 下单后观察：① DB 中 `orders` + `outbox_messages` 同时出现 → ② 后台投递到 MQ → ③ 消费者终端输出
3. **模拟死信场景**：临时断开 RabbitMQ 网络，下单后查看 `outbox_messages` 表中 retry_count 递增和 next_retry_at 变化；恢复网络后观察自动重投递
4. 调用 `GET /admin/outbox/dead-letters?status=failed` 查看死信列表，用 `POST /admin/outbox/{id}/retry` 手动重试

**思考题**：
- 为什么订单服务要通过 HTTP 调商品服务扣库存，而不是直接操作商品数据库？
- 发送订单消息为什么用 MQ 而不是直接 HTTP 调通知服务？（解耦、削峰、异步）

---

## 阶段 3：网关 & 分布式治理（核心）

**目标**：理解 API 网关在分布式系统中的"守门人"角色

| 顺序 | 学习内容 | 对应文件 | 要点 |
|------|---------|---------|------|
| 3.1 | 服务注册与发现 | `gateway/main.py` `ServiceDiscovery` | Nacos 原理：服务启动时注册 → 网关从 Nacos 发现地址 → 动态路由 |
| 3.2 | 统一入口 & 路由转发 | `gateway/main.py` `gateway_route()` | `SERVICE_ROUTES` 路径前缀匹配；`httpx` 透传请求；为什么要统一入口？ |
| 3.3 | JWT 鉴权中间件 | `gateway/main.py` `AuthMiddleware` | 白名单机制；`Depends` 注入鉴权；为什么鉴权放网关而不是每个服务自己做？ |
| 3.4 | IP 滑动窗口限流 | `gateway/main.py` `RateLimiter` | 固定窗口 vs 滑动窗口；限流保护后端不被刷爆 |
| 3.5 | 熔断器 | `gateway/main.py` `CircuitBreaker` | Closed → Open → Half-Open 状态机；防止服务雪崩；连续失败 N 次触发 |
| 3.6 | 监控端点 | `/health` `/metrics/gateway` | 健康检查给 K8s/Docker 探针用；指标暴露给 Prometheus |

**动手**：
1. 启动全部服务，通过网关 8000 调接口（不走 8001/8002/8003）
2. 快速连续发请求，触发限流
3. 停掉商品服务后发下单请求，观察熔断触发

---

## 阶段 4：分布式核心难题攻克

**目标**：理解分布式系统最难的部分，对比当前项目的不足

| 顺序 | 学习内容 | 参考章节 | 要点 |
|------|---------|---------|------|
| 4.1 | 分布式事务问题 | `GAP-ANALYSIS.md` § 三 | 当前下单流程的风险：扣库存成功但写订单失败→库存丢失；理解 ACID vs BASE |
| 4.2 | 方案对比：Seata / TCC / Saga / 本地消息表 | `GAP-ANALYSIS.md` 对照表 | 各方案的适用场景和复杂度；本项目推荐"本地消息表" |
| 4.3 | **本地消息表增强版（Outbox Pattern v2）** | `order-service/models.py` + `main.py` | 模型字段设计（message_id/schema_version/next_retry_at/索引）；指数退避 vs 固定间隔重试；`SKIP LOCKED` 行级锁防多实例重复投递；分批 commit 减少 DB IO |
| 4.4 | **死信队列（Dead Letter Queue）管理** | `order-service/main.py` Admin API | 为什么需要死信管理？3 个接口：查询/重试/统计；生产运维如何处理 failed 消息 |
| 4.5 | 幂等性设计（双层） | — | **写入幂等**：`idempotency_key` 防止重复下单；**消费幂等**：`message_id` 防止 MQ 重复消费导致数据异常 |
| 4.6 | 分布式链路追踪 | `GAP-ANALYSIS.md` § 五 | TraceID → SpanID 全链路关联；OpenTelemetry + Jaeger |

**思考题**：
- 如果扣库存成功但后续订单写入失败，怎么回滚库存？
- `idempotency_key` 已经有唯一索引防重复下单，为什么还需要 `message_id`？（提示：一个是写入幂等，一个是消费幂等）
- 指数退避（10s→20s→40s）比固定间隔重试好在哪里？
- 多实例部署时，两个服务同时扫到同一条 pending 消息怎么办？`SKIP LOCKED` 如何解决？

---

## 阶段 5：可观测性 & 运维

**目标**：理解生产环境如何监控和运维微服务

| 顺序 | 学习内容 | 参考/文件 | 要点 |
|------|---------|----------|------|
| 5.1 | 结构化日志 | `GAP-ANALYSIS.md` § 五 | 简单 `print` → 结构化 JSON 日志；TraceID 贯穿所有日志 |
| 5.2 | Prometheus + Grafana | `GAP-ANALYSIS.md` | 指标暴露 → Prometheus 采集 → Grafana 可视化面板 + 告警规则 |
| 5.3 | Dockerfile 多阶段构建 | `GAP-ANALYSIS.md` § 六 | 减小镜像体积；分离构建依赖和运行依赖 |
| 5.4 | 优雅停机 | — | `SIGTERM` → 等待现有请求完成 → 释放 DB/Redis/MQ 连接 → 退出 |
| 5.5 | CI/CD 流水线 | `GAP-ANALYSIS.md` § 六 | Push → 自动测试 → 构建镜像 → 部署 |

---

## 阶段 6：测试体系

**目标**：建立测试意识——当前项目 0% 测试覆盖

| 顺序 | 学习内容 | 参考 | 要点 |
|------|---------|------|------|
| 6.1 | pytest 基础 | — | fixtures、parametrize、async tests (`pytest-asyncio`) |
| 6.2 | 单元测试 | `GAP-ANALYSIS.md` § 四 | 密码哈希正确性、JWT 签发/验证、限流逻辑、熔断状态机 |
| 6.3 | 集成测试 | `GAP-ANALYSIS.md` § 四 | 全链路：注册→登录→加商品→下单→验证库存扣减 |
| 6.4 | Mock 外部依赖 | — | Mock Redis/RabbitMQ/Nacos，使测试不依赖真实中间件 |

---

## 阶段 7：生产级增强

**目标**：补齐企业级最后一块拼图

| 顺序 | 学习内容 | 要点 |
|------|---------|------|
| 7.1 | K8s 部署 | 将 docker-compose 迁移到 K8s Deployment + Service + Ingress |
| 7.2 | Nacos Config 热更新 | 替代 `.env` 文件，配置变更无需重启 |
| 7.3 | HTTPS/TLS | Nginx 反向代理 + Let's Encrypt 证书 |
| 7.4 | API 版本管理 | `/api/v1/user/register`，多版本共存 |

---

## 建议的学习节奏

```
第1天：阶段 0（环境搭建 + 架构理解）
第2天：阶段 1（配置管理 + 异常处理）
第3天：阶段 2.1~2.2（用户服务 + 商品服务）
第4天：阶段 2.3（订单服务 + Outbox 增强版 + 死信管理）
第5天：阶段 3.1~3.3（服务发现 + 路由 + JWT 鉴权）
第6天：阶段 3.4~3.6（限流 + 熔断 + 监控）
第7天：阶段 4（分布式事务/幂等/链路追踪理论）
第8天：阶段 5（日志/监控/容器化）
第9-10天：阶段 6（写测试）
```

**关键原则**：
1. 每个阶段先读代码，再看 README 中对应的解释
2. 每学完一个服务就启动它，用 Swagger 实际调接口验证
3. 遇到概念不理解（如"熔断"、"分布式事务"），先看本项目实现，再查资料深入
4. **GAP-ANALYSIS.md** 是"差距地图"——告诉你离企业级还差什么，指引下一步方向
5. **README.md** 是"操作手册"——每个服务的启动、接口调用、现象验证，按步骤操作即可跑通
