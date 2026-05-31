## 1. 启动全服务并确认网关路由正常

- [x] 1.1 确认所有服务容器运行中（gateway/user/goods/order/mq-consumer）
- [x] 1.2 通过网关 8080 登录获取 token，调 goods 和 order 接口验证路由通畅

## 2. 限流测试

- [x] 2.1 用并发脚本快速向网关发送 15 个请求（>10 req/s 阈值），观察至少 1 个返回 429
- [x] 2.2 等待 1 秒窗口过后再发请求，确认恢复正常

## 3. 熔断测试

- [x] 3.1 查看 /metrics/gateway 确认熔断器初始状态为 closed（修复 metrics 路由被通配路由拦截的问题）
- [x] 3.2 停下 ms-goods-service 容器
- [x] 3.3 通过网关连续发送 6+ 个 /goods/* 请求，前 5 次返回连接失败，第 6 次返回 503 "服务 goods-service 暂时不可用"
- [x] 3.4 查看 /metrics/gateway 确认熔断器状态变为 open
- [x] 3.5 等待 30 秒后重启 goods-service，发请求确认熔断恢复（请求正常返回）
