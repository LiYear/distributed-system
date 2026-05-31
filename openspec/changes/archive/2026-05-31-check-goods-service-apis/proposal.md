## Why

商品服务（goods-service）是微服务系统中的核心模块，负责商品 CRUD 和库存管理，并引入了 Redis 缓存、分布式锁等机制。前端用户已注册成功，下一步需要验证商品服务的 4 个接口是否全部正常可用，确保缓存穿透/击穿/雪崩防护逻辑在真实运行环境中正确工作。

## What Changes

- 逐接口验证 goods-service：健康检查、添加商品、查询商品（含缓存逻辑）、扣减库存
- 验证通过网关（8080）和直连（8002）两种方式均可正常调用
- 验证 Redis 缓存命中、分布式锁、空值标记、TTL 随机抖动等机制是否生效
- 如发现接口不可用或行为异常，定位并修复根因

## Capabilities

### New Capabilities

- `goods-api-verification`: 对 goods-service 的 4 个接口进行功能验证，包括健康检查、商品添加、商品查询（含缓存逻辑验证）、库存扣减，确保通过网关和直连两种方式均可正常调用

### Modified Capabilities

<!-- No existing specs to modify -->

## Impact

- 受影响代码：`goods-service/main.py`、`gateway/main.py`（路由转发）
- 受影响服务：ms-goods-service (8002)、ms-gateway (8080)
- 依赖基础设施：MySQL（db_goods 库）、Redis（缓存）、Nacos（服务发现）
