## 1. 添加 mq_consumer 服务到 docker-compose

- [x] 1.1 在 docker-compose.yml 中添加 mq_consumer 服务定义，使用同一 Dockerfile，command 运行 `python -u order-service/mq_consumer.py`

## 2. 部署并启动

- [x] 2.1 重建并启动 mq_consumer 服务
- [x] 2.2 验证 mq_consumer 容器正在运行，日志显示 "订单消息消费者已启动，等待消息..."

## 3. 创建订单并观察 MQ 消息

- [x] 3.1 选择一个可用的 user_id 和 goods_id 发起 POST /order/create 创建订单
- [x] 3.2 查看 mq_consumer 容器日志，确认输出 "收到订单消息：{...}"，内容匹配下单信息
- [x] 3.3 测试库存不足场景，确认不会创建订单也不会发 MQ 消息

## 4. 问题修复（如有）

- [x] 4.1 修复 order-service 调用 goods-service host 错误（SERVICE_IP→新增 GOODS_SERVICE_HOST 环境变量，默认 goods-service），订单创建和 MQ 消息验证通过
