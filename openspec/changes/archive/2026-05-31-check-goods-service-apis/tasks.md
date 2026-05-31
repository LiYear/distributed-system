## 1. 健康检查验证

- [x] 1.1 直连 goods-service (8002) 验证 GET /health 返回 `{"status": "ok"}`
- [x] 1.2 通过网关 (8080) 验证 GET /health 返回 `{"status": "ok"}`

## 2. 添加商品验证

- [x] 2.1 直连 goods-service 验证 POST /goods/add 成功添加商品并返回完整数据
- [x] 2.2 直连 goods-service 验证 POST /goods/add 缺少必填字段时返回 422 校验错误
- [x] 2.3 通过网关 (8080) 验证 POST /goods/add 成功添加商品

## 3. 查询商品及缓存验证

- [x] 3.1 直连 8002 查询已存在商品 GET /goods/{id}，首次查 DB 后写入 Redis 缓存
- [x] 3.2 直连 8002 再次查询同一商品，确认缓存命中（响应时间更短）
- [x] 3.3 直连 8002 查询不存在商品 GET /goods/{id}，返回 404 并缓存空值标记
- [x] 3.4 通过网关 (8080) 查询商品 GET /goods/{id} 正常返回

## 4. 库存扣减验证

- [x] 4.1 直连 8002 验证 PUT /goods/stock/{id}?num=N 成功扣减库存并删除缓存
- [x] 4.2 直连 8002 验证库存不足时返回 400 "库存不足"
- [x] 4.3 通过网关 (8080) 验证扣减库存正常

## 5. 问题修复（如有）

- [x] 5.1 修复 Nacos 注册问题：docker-compose 按服务设置 SERVICE_IP（gateway/user-service/goods-service/order-service），修复 heartbeat_interval=5，修复网关 query 参数转发缺失
