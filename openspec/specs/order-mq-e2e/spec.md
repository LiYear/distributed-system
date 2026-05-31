## ADDED Requirements

### Requirement: mq_consumer as docker-compose service
The system SHALL deploy mq_consumer as a docker-compose service that connects to RabbitMQ and consumes the `order_notify_queue`.

#### Scenario: mq_consumer starts and waits for messages
- **WHEN** docker-compose starts the mq_consumer service
- **THEN** the service connects to RabbitMQ, declares `order_notify_queue`, and prints "订单消息消费者已启动，等待消息..."

### Requirement: Order creation triggers MQ message delivery
The system SHALL publish an order notification message to `order_notify_queue` after successful order creation.

#### Scenario: Order created and consumer receives message
- **WHEN** client sends POST /order/create with valid `{user_id, goods_id, buy_num}`
- **THEN** goods stock is deducted, order is saved to database, message containing order_no, user_id, and total_price is published to RabbitMQ, and mq_consumer prints "收到订单消息：{...}"

#### Scenario: Order creation fails on insufficient stock
- **WHEN** client sends POST /order/create with buy_num exceeding available stock
- **THEN** no order is created and no MQ message is published

### Requirement: mq_consumer log verification
The system SHALL make mq_consumer output observable via docker logs.

#### Scenario: Check consumer logs after order
- **WHEN** an order is created via API
- **THEN** `docker logs ms-mq-consumer` shows the received message content matching the created order
