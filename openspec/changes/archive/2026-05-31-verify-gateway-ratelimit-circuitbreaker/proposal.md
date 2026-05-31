## Why

网关实现了两大防护能力——IP 限流（10 req/s）和熔断器（5 次连续失败→30s 熔断），但尚未验证在生产环境中是否真正生效。需要通过实际操作触发限流和熔断，观察网关行为是否符合设计预期。

## What Changes

- 启动全部服务，仅通过网关 (8080) 调用接口验证路由正常
- 用脚本快速连续发请求，超过 10 req/s 阈值后验证返回 429
- 停下 goods-service 容器后通过网关发下单请求，连续 5 次失败后验证熔断器打开，返回 503
- 通过 /metrics/gateway 观察熔断器状态变化，30s 后验证自动恢复

## Capabilities

### New Capabilities

- `gateway-ratelimit`: 验证网关 IP 限流功能——单 IP 在 1 秒窗口内超过 10 次请求后返回 429
- `gateway-circuitbreaker`: 验证网关熔断功能——下游服务连续 5 次不可用后熔断打开，30s 后半开恢复

### Modified Capabilities

<!-- No existing specs to modify -->

## Impact

- 受影响服务：ms-gateway (8080)、ms-goods-service (8002)
- 网关配置：.env 中 RATE_LIMIT_MAX_REQUESTS=10, RATE_LIMIT_WINDOW_SECONDS=1, CB_FAILURE_THRESHOLD=5, CB_TIMEOUT_SECONDS=30
- 无代码修改，纯行为验证