## Context

网关限流器和熔断器已在代码中实现但未经手工触发验证：

- **限流器**：基于 IP，滑动窗口，阈值 10 req/s。`is_allowed()` 逐请求判断，`requests` dict 在内存中
- **熔断器**：按目标端口（8001/8002/8003）独立跟踪，5 次连续失败→open(30s)→half_open→成功恢复 closed。状态可通过 `/metrics/gateway` 查看
- 网关端口 8080，所有后端服务已部署且 Nacos 注册正常

## Goals / Non-Goals

**Goals:**
- 验证路由正常：登录→拿 token→调 goods/order 接口
- 触发限流：10+ req/s → 429
- 触发熔断：停下 goods-service → 连续 5 次失败 → 503 → 30s 恢复

**Non-Goals:**
- 不修改 gateway 代码
- 不修改限流/熔断阈值配置

## Decisions

1. **限流测试用 shell 循环**：`for i in $(seq 1 15); do curl & done` 并发发请求，观察 429 响应
2. **熔断测试步骤**：先确认 goods 接口正常 → `docker stop ms-goods-service` → 连续发 5 次请求制造失败 → 第 6 次应返回 503 → 30s 后再试应恢复
3. **用 /metrics/gateway 观察状态**：每个阶段查一次以确认熔断器状态转换

## Risks / Trade-offs

- 限流测试会短期影响其他 API 调用 → 窗口仅 1 秒，影响极小
- 停 goods-service 会短暂中断商品查询 → 30s 后自动恢复
