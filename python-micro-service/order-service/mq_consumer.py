import asyncio
import aio_pika


async def main():
    # 连接 RabbitMQ
    connection = await aio_pika.connect_robust(
        host="localhost",
        login="admin",
        password="admin123"
    )
    channel = await connection.channel()
    # 声明队列
    queue = await channel.declare_queue("order_notify_queue", durable=True)
    print("订单消息消费者已启动，等待消息...")

    async for message in queue:
        async with message.process():
            body = message.body.decode()
            print(f"收到订单消息：{body}")


if __name__ == "__main__":
    asyncio.run(main())
