## Why

订单服务通过 RabbitMQ 发送下单通知，mq_consumer 是独立的消费脚本。此前只验证了 user-service 和 goods-service 接口，订单服务的消息队列环节尚未端到端验证。需要在 docker-compose 中同时启动 mq_consumer，创建订单后观察消费者是否正确收到消息，确认 RabbitMQ 异步通知链路通畅。

## What Changes

- 将 mq_consumer 添加为 docker-compose 服务，随订单服务同时启动
- 向 order-service 发送创建订单请求，触发 RabbitMQ 消息投递
- 查看 mq_consumer 容器日志，验证消费者收到正确的订单消息
- 验证订单创建全链路：API 请求 → 扣库存（调用 goods-service）→ 写数据库 → 发 MQ 消息 → 消费者输出

## Capabilities

### New Capabilities

- `order-mq-e2e`: 验证订单创建到 RabbitMQ 消费者接收消息的端到端流程，包括 mq_consumer 作为 docker-compose 服务的部署配置

### Modified Capabilities

<!-- No existing specs to modify -->

## Impact

- `docker-compose.yml`：新增 mq_consumer 服务定义
- `order-service/mq_consumer.py`：消费者脚本（无需修改代码）
- 依赖：RabbitMQ（order_notify_queue）、goods-service（扣库存）、MySQL（写订单）
