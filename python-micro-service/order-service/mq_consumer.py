import asyncio
import logging
import os
import sys

import aio_pika

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASSWORD, validate_config
validate_config("Order-Consumer", ["RABBITMQ_PASSWORD"])

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
)
logger = logging.getLogger("order-consumer")

MAX_RETRIES = 3  # 单条消息最大重试次数
RECONNECT_DELAY = 5  # 连接断开后重连等待秒数


async def process_message(body: str) -> bool:
    """
    处理单条订单消息。

    Returns:
        True: 处理成功
        False: 处理失败（可重试）
    Raises:
        ValueError: 消息格式错误（不可重试，直接丢弃）
    """
    logger.info("[处理消息] 收到订单通知: %s", body)
    # TODO: 在此添加实际业务逻辑（如发送邮件、推送通知等）
    return True


async def main():
    """带自动重连的消费者主循环"""
    while True:
        connection = None
        try:
            connection = await aio_pika.connect_robust(
                host=RABBITMQ_HOST, login=RABBITMQ_USER, password=RABBITMQ_PASSWORD
            )
            channel = await connection.channel()
            # 设置 prefetch_count 控制并发消费数量
            await channel.set_qos(prefetch_count=10)
            queue = await channel.declare_queue("order_notify_queue", durable=True)
            logger.info("订单消息消费者已启动，等待消息...")

            async for message in queue:
                async with message.process(requeue=False):  # 手动控制重入队列
                    retry_count = 0
                    body = message.body.decode()
                    success = False

                    while retry_count <= MAX_RETRIES and not success:
                        try:
                            success = await process_message(body)
                            if success:
                                logger.info("[消费成功] message_id=%s", message.message_id)
                        except ValueError as e:
                            # 消息格式等不可恢复的错误 → 直接确认（丢弃），不重试
                            logger.error("[消息丢弃] 格式错误，无法处理: %s | body=%s", e, body)
                            break
                        except Exception as e:
                            retry_count += 1
                            if retry_count <= MAX_RETRIES:
                                logger.warning(
                                    "[消费失败] 第 %d/%d 次重试: %s",
                                    retry_count, MAX_RETRIES, e,
                                )
                                await asyncio.sleep(1 * retry_count)  # 指数退避
                            else:
                                logger.error(
                                    "[消费最终失败] 达到最大重试次数(%d)，消息进入死信: %s",
                                    MAX_RETRIES, e,
                                )

        except aio_pika.AMQPConnectionError as e:
            logger.error("[连接断开] RabbitMQ 连接异常: %s，%ds 后重连...", e, RECONNECT_DELAY)
            if connection:
                await connection.close()
            await asyncio.sleep(RECONNECT_DELAY)
        except KeyboardInterrupt:
            logger.info("消费者收到退出信号，正在关闭...")
            if connection:
                await connection.close()
            break
        except Exception as e:
            logger.error("[未知异常] 消费者发生未预期异常: %s", e, exc_info=True)
            await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    asyncio.run(main())
