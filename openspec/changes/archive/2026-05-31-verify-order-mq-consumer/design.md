## Context

order-service 在创建订单时调用 `send_order_msg()`，将订单信息发布到 RabbitMQ 的 `order_notify_queue` 队列。`mq_consumer.py` 是独立的消费者脚本，连接同一 RabbitMQ 并消费该队列——但它没有被 docker-compose 管理，需要手动启动。用户已为各服务添加 `--reload` 和 volume 挂载用于热更新。

当前 docker-compose 中 order-service 容器包含 mq_consumer.py 文件，但没有独立运行消费者脚本，需新增一个服务容器来运行它。

## Goals / Non-Goals

**Goals:**
- 在 docker-compose.yml 中添加 mq_consumer 服务，与 order-service 共用同一服务镜像
- 验证：创建订单 → goods-service 扣库存 → 写 MySQL → MQ 消息投递 → mq_consumer 输出
- 通过 docker logs 直接观察消费者终端输出

**Non-Goals:**
- 不修改 mq_consumer.py 逻辑（脚本本身已正确）
- 不修改 order-service 的下单流程

## Decisions

1. **mq_consumer 作为独立容器**：使用同一 Dockerfile 构建，command 运行 `python mq_consumer.py`，共享 ms-network 网络
2. **不暴露端口**：消费者不需要对外端口，仅内部消费 MQ 消息
3. **依赖 RabbitMQ 健康**：设置 `depends_on` 确保 RabbitMQ 就绪后再启动
4. **验证方式**：curl 创建订单后直接 `docker logs ms-mq-consumer` 检查输出

## Risks / Trade-offs

- mq_consumer 是简单的单线程脚本，无重连机制 → 如果 RabbitMQ 重启后可能需手动重启消费者容器
- 不使用 --reload 标志（消费者不是 HTTP 服务，不需要热重载）
