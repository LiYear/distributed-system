## Context

goods-service 提供商品添加、查询、库存扣减 4 个接口，引入了 Redis 缓存（Cache-Aside 模式 + 分布式锁 + 空值标记 + TTL 随机抖动）。上一次 session 已修复 Nacos 服务注册和网关转发问题，user-service 通过网关验证通过。现在按同样方式验证 goods-service。

当前环境状态：所有 Docker 容器运行中（ms-gateway、ms-user-service、ms-goods-service、ms-order-service、ms-mysql、ms-redis、ms-nacos、ms-rabbitmq）。

## Goals / Non-Goals

**Goals:**
- 验证 goods-service 的 4 个接口（health、add、get、deduct stock）通过网关和直连均可正常调用
- 验证 Redis 缓存逻辑（缓存写入、命中、空值标记）正确工作
- 如发现接口异常，定位根因并修复

**Non-Goals:**
- 不修改 goods-service 的业务逻辑
- 不涉及 order-service 调用 goods-service 的 bug（那是 order-service 的问题）

## Decisions

1. **测试顺序**：先直连 8002 验证，再通过网关 8080 验证，与 user-service 验证方式一致
2. **缓存验证方式**：添加商品后连续两次查询同一 ID，第二次应命中 Redis 缓存（响应时间更短）
3. **测试工具**：使用 curl 命令行直接调用 API，不引入额外测试框架

## Risks / Trade-offs

- 测试数据会残留（db_goods 表中），不影响后续使用
- 如果 Nacos 服务发现再次出问题，网关测试会失败 → 复用上次修复的 fallback 机制
