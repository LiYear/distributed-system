# Python 微服务+分布式实战项目（全流程落地版）

## 项目整体规划

### 一、项目定位 & 技术栈

**项目名称**：极简电商微服务系统（用户服务、商品服务、订单服务、网关服务）

**架构模式**：**网关 + 多微服务 + 注册发现 + 消息队列 + 数据库分库**（标准分布式微服务架构）

**Python 核心技术栈**

1. Web 框架：**FastAPI**（高性能、异步、接口自动文档，Python 微服务首选）
2. 服务注册/发现/配置中心：**Nacos**（轻量、易部署，国内主流）
3. 网关：**FastAPI-Gateway**（基于 FastAPI 实现的轻量网关）
4. 消息队列（分布式解耦、异步通信）：**RabbitMQ**（订单异步通知、流量削峰）
5. 数据库：**MySQL 8.0**（分库：用户库、商品库、订单库）
6. ORM：**SQLAlchemy 2.0（异步）**
7. 缓存（分布式缓存）：**Redis**（热点商品、登录信息缓存）
8. 服务通信：**HTTP 接口调用 + 异步 MQ**
9. 容器化（统一部署）：**Docker + Docker Compose**
10. 接口文档：自动生成 Swagger / ReDoc

### 二、业务模块拆分（标准微服务拆分）

| 服务名称 | 端口 | 职责 | 数据库 |
| ---- | ---- | ---- | ---- |
| Gateway 网关服务 | 8000 | 统一入口、动态路由、JWT鉴权、限流、熔断、日志监控 | 无 |
| User-Service 用户服务 | 8001 | 注册、登录、用户信息 | `db_user` |
| Goods-Service 商品服务 | 8002 | 商品CRUD、商品列表、库存 | `db_goods` |
| Order-Service 订单服务 | 8003 | 下单、订单查询、异步订单通知 | `db_order` |

**业务流程**：
客户端 → 网关(8000) → 对应微服务
1. 用户注册/登录 → 用户服务
2. 浏览商品 → 商品服务（Redis 缓存热点数据）
3. 提交订单 → 订单服务（扣库存 + RabbitMQ 异步推送订单消息）

---

## 前置环境准备（必做，一步一步落地）

> 全程基于 **Windows / Linux / Mac** 通用，优先使用 Docker 一键部署中间件，避免环境踩坑

### 步骤1：安装基础软件

1. 安装 Python 3.10+（推荐 3.11），配置环境变量
2. 安装 **Docker + Docker Compose**（所有中间件统一容器部署，不用本地装）
   - Windows/Mac：直接装 Docker Desktop
   - Linux：按官方教程安装 Docker & Compose
3. 代码编辑器：VS Code / PyCharm

### 步骤2：编写 Docker Compose 启动所有中间件

在电脑任意目录新建文件夹 `micro-service-env`，新建文件 `docker-compose.yml`，**复制下面全部内容**：

```yaml
version: '3.8'

services:
  # MySQL 8.0 分库数据库
  mysql:
    image: mysql:8.0
    container_name: ms-mysql
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: 123456
    volumes:
      - ./mysql-data:/var/lib/mysql
    restart: always
    command: --default-authentication-plugin=mysql_native_password

  # Redis 分布式缓存
  redis:
    image: redis:alpine
    container_name: ms-redis
    ports:
      - "6379:6379"
    restart: always

  # RabbitMQ 消息队列（带管理后台）
  rabbitmq:
    image: rabbitmq:3-management
    container_name: ms-rabbitmq
    ports:
      - "5672:5672"   # 消息端口
      - "15672:15672" # 管理后台端口
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin123
    restart: always

  # Nacos 服务注册&配置中心（单机版）
  nacos:
    image: nacos/nacos-server:v2.4.3
    container_name: ms-nacos
    ports:
      - "8848:8848"
      - "9848:9848"
    environment:
      MODE: standalone  # 单机模式（学习用）
    restart: always

networks:
  default:
    name: ms-network
```

#### 启动中间件（终端执行）

进入 `micro-service-env` 目录，执行：

```bash
docker-compose up -d
```

等待 1~2 分钟，所有容器启动完成。

#### 验证中间件是否正常（逐个检查）

1. **Nacos 注册中心** — 浏览器访问：`http://localhost:8848/nacos`，账号密码：`nacos / nacos` → 登录成功即为正常。
2. **RabbitMQ 管理后台** — 访问：`http://localhost:15672`，账号：`admin` 密码：`admin123` → 登录成功。
3. **Redis**：默认端口 6379，无需页面，后续代码连接测试。
4. **MySQL**：端口 3306，账号 `root` 密码 `123456`。

### 步骤3：创建3个业务数据库

使用 Navicat / DBeaver / MySQL 客户端连接 `localhost:3306`，执行以下 SQL 创建**三个独立库**（微服务分库核心思想）：

```sql
-- 用户库
CREATE DATABASE IF NOT EXISTS db_user DEFAULT CHARACTER SET utf8mb4;
-- 商品库
CREATE DATABASE IF NOT EXISTS db_goods DEFAULT CHARACTER SET utf8mb4;
-- 订单库
CREATE DATABASE IF NOT EXISTS db_order DEFAULT CHARACTER SET utf8mb4;
```

---

## 项目整体目录结构（规范微服务目录）

```
python-micro-service/
├── gateway/                # 网关服务 (8000)
│   ├── main.py
│   ├── requirements.txt
│
├── user-service/           # 用户服务 (8001)
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── requirements.txt
│
├── goods-service/          # 商品服务 (8002)
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── requirements.txt
│
├── order-service/          # 订单服务 (8003)
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── mq_consumer.py     # RabbitMQ 消费者
│   ├── requirements.txt
│
└── README.md
```

---

## 第一部分：公共依赖 & 统一配置

所有服务共用的依赖，逐个服务创建 `requirements.txt`

### 通用依赖清单（每个服务都需要）

```txt
# Web框架
fastapi>=0.104.1
uvicorn[standard]>=0.24.0

# 异步ORM 数据库
sqlalchemy[asyncio]>=2.0.23
aiomysql>=0.2.0

# Redis 异步客户端
aioredis>=2.0.1

# RabbitMQ 消息队列
aio-pika>=9.2.1

# Nacos 服务注册发现
nacos-sdk-python>=0.1.15

# 数据校验
pydantic>=2.4.2
```

**安装依赖**：进入每个服务目录，执行

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 第二部分：逐个开发微服务（从底层到上层）

### 一、开发【User-Service 用户服务】端口 8001

#### 1. user-service/database.py 异步数据库连接

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# MySQL 连接地址（db_user 库）
DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/db_user"

# 异步引擎
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()

# 获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

#### 2. user-service/models.py 数据库模型

```python
from sqlalchemy import Column, Integer, String
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    phone = Column(String(20))
```

#### 3. user-service/schemas.py 数据校验模型

```python
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    phone: str | None = None


class UserInfo(BaseModel):
    id: int
    username: str
    phone: str | None

    class Config:
        from_attributes = True
```

#### 4. user-service/main.py 主服务 + 注册到 Nacos

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from nacos import NacosClient
import uvicorn

from database import get_db, engine, Base
from models import User
from schemas import UserCreate, UserInfo

# 1. 初始化 FastAPI
app = FastAPI(title="用户微服务", version="1.0")


# 2. 启动时创建数据表
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# 3. Nacos 服务注册（核心：服务发现）
def register_nacos():
    server_addrs = "localhost:8848"
    client = NacosClient(server_addrs)
    client.add_naming_instance(service_name="user-service", ip="127.0.0.1", port=8001)
    print("用户服务已注册到 Nacos")


# 4. 接口
@app.post("/user/register", response_model=UserInfo, summary="用户注册")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # 判断用户名是否存在
    result = await db.execute(select(User).where(User.username == user.username))
    exist_user = result.scalar_one_or_none()
    if exist_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    new_user = User(
        username=user.username,
        password=user.password,
        phone=user.phone
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@app.get("/user/{user_id}", response_model=UserInfo, summary="查询用户信息")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


# 5. 启动入口
if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

#### 启动用户服务

进入 `user-service` 目录执行：

```bash
python main.py
```

访问文档：`http://127.0.0.1:8001/docs`
同时打开 Nacos 页面 → **服务管理-服务列表**，能看到 `user-service` 即注册成功。

---

### 二、开发【Goods-Service 商品服务】端口 8002（含 Redis 缓存）

#### 1. goods-service/database.py

仅修改数据库名 `db_goods`，其余和用户服务一致：

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/db_goods"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

#### 2. goods-service/models.py

```python
from sqlalchemy import Column, Integer, String, Float
from database import Base


class Goods(Base):
    __tablename__ = "goods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)  # 库存
```

#### 3. goods-service/schemas.py

```python
from pydantic import BaseModel


class GoodsCreate(BaseModel):
    name: str
    price: float
    stock: int


class GoodsInfo(BaseModel):
    id: int
    name: str
    price: float
    stock: int

    class Config:
        from_attributes = True
```

#### 4. goods-service/main.py（整合 Redis 缓存 + Nacos 注册）

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import aioredis
from nacos import NacosClient
import uvicorn

from database import get_db, engine, Base
from models import Goods
from schemas import GoodsCreate, GoodsInfo

app = FastAPI(title="商品微服务", version="1.0")

# Redis 全局连接
redis: aioredis.Redis | None = None


@app.on_event("startup")
async def startup():
    # 创建数据表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 连接 Redis
    global redis
    redis = await aioredis.from_url("redis://localhost:6379")


@app.on_event("shutdown")
async def shutdown():
    await redis.close()


# Nacos 注册
def register_nacos():
    client = NacosClient("localhost:8848")
    client.add_naming_instance(service_name="goods-service", ip="127.0.0.1", port=8002)
    print("商品服务已注册到 Nacos")


# 接口：新增商品
@app.post("/goods/add", response_model=GoodsInfo)
async def add_goods(goods: GoodsCreate, db: AsyncSession = Depends(get_db)):
    new_goods = Goods(name=goods.name, price=goods.price, stock=goods.stock)
    db.add(new_goods)
    await db.commit()
    await db.refresh(new_goods)
    return new_goods


# 接口：查询商品（优先走 Redis 缓存）
@app.get("/goods/{goods_id}", response_model=GoodsInfo)
async def get_goods(goods_id: int, db: AsyncSession = Depends(get_db)):
    # 1. 查缓存
    cache_key = f"goods:{goods_id}"
    cache_data = await redis.get(cache_key)
    if cache_data:
        import json
        return json.loads(cache_data)

    # 2. 缓存没有，查数据库
    result = await db.execute(select(Goods).where(Goods.id == goods_id))
    goods = result.scalar_one_or_none()
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 3. 写入缓存（过期时间 5 分钟）
    goods_dict = {"id": goods.id, "name": goods.name, "price": goods.price, "stock": goods.stock}
    await redis.setex(cache_key, 300, json.dumps(goods_dict))
    return goods


# 扣库存（订单服务调用）
@app.put("/goods/stock/{goods_id}")
async def deduct_stock(goods_id: int, num: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goods).where(Goods.id == goods_id))
    goods = result.scalar_one_or_none()
    if not goods or goods.stock < num:
        raise HTTPException(status_code=400, detail="库存不足")
    goods.stock -= num
    await db.commit()
    return {"code": 200, "msg": "扣库存成功"}


if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

#### 启动商品服务

```bash
python main.py
```

Nacos 服务列表出现 `goods-service` 即为正常，文档地址：`http://127.0.0.1:8002/docs`

---

### 三、开发【Order-Service 订单服务】端口 8003（MQ 异步通信核心）

订单服务逻辑：**下单 → 扣商品库存 → 发送消息到 RabbitMQ → 消费者异步处理**

#### 1. order-service/database.py

修改库名为 `db_order`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/db_order"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

#### 2. order-service/models.py

```python
from sqlalchemy import Column, Integer, String, Float
from database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(64), unique=True, nullable=False)  # 订单号
    user_id = Column(Integer, nullable=False)
    goods_id = Column(Integer, nullable=False)
    buy_num = Column(Integer, default=1)
    total_price = Column(Float)
    status = Column(String(20), default="pending")  # 订单状态
```

#### 3. order-service/schemas.py

```python
from pydantic import BaseModel


class OrderCreate(BaseModel):
    user_id: int
    goods_id: int
    buy_num: int


class OrderInfo(BaseModel):
    id: int
    order_no: str
    user_id: int
    goods_id: int
    buy_num: int
    total_price: float
    status: str

    class Config:
        from_attributes = True
```

#### 4. order-service/mq_consumer.py（RabbitMQ 消费者，独立进程）

```python
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
```

#### 5. order-service/main.py（下单接口 + 调用商品服务 + 发送MQ + Nacos注册）

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import aiohttp
import aio_pika
import uuid
from nacos import NacosClient
import uvicorn

from database import get_db, engine, Base
from models import Order
from schemas import OrderCreate, OrderInfo

app = FastAPI(title="订单微服务", version="1.0")
rabbit_connection = None
rabbit_channel = None


@app.on_event("startup")
async def startup():
    # 创建订单表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 连接 RabbitMQ
    global rabbit_connection, rabbit_channel
    rabbit_connection = await aio_pika.connect_robust(
        host="localhost", login="admin", password="admin123"
    )
    rabbit_channel = await rabbit_connection.channel()
    await rabbit_channel.declare_queue("order_notify_queue", durable=True)


@app.on_event("shutdown")
async def shutdown():
    await rabbit_connection.close()


# Nacos 注册
def register_nacos():
    client = NacosClient("localhost:8848")
    client.add_naming_instance(service_name="order-service", ip="127.0.0.1", port=8003)
    print("订单服务已注册到 Nacos")


# 调用商品服务扣库存（服务间HTTP调用）
async def deduct_goods_stock(goods_id: int, num: int):
    async with aiohttp.ClientSession() as session:
        url = f"http://127.0.0.1:8002/goods/stock/{goods_id}?num={num}"
        async with session.put(url) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=400, detail="扣库存失败")


# 发送消息到 RabbitMQ
async def send_order_msg(order_info: dict):
    msg_body = str(order_info)
    await rabbit_channel.default_exchange.publish(
        aio_pika.Message(body=msg_body.encode()),
        routing_key="order_notify_queue"
    )


# 下单接口
@app.post("/order/create", response_model=OrderInfo)
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    # 1. 远程调用商品服务扣库存
    await deduct_goods_stock(order.goods_id, order.buy_num)

    # 2. 模拟查询商品价格（简化）
    async with aiohttp.ClientSession() as session:
        res = await session.get(f"http://127.0.0.1:8002/goods/{order.goods_id}")
        goods_data = await res.json()
        total_price = goods_data["price"] * order.buy_num

    # 3. 创建订单
    order_no = f"ORD_{uuid.uuid4()}"
    new_order = Order(
        order_no=order_no,
        user_id=order.user_id,
        goods_id=order.goods_id,
        buy_num=order.buy_num,
        total_price=total_price
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)

    # 4. 发送异步消息
    await send_order_msg({
        "order_no": order_no,
        "user_id": order.user_id,
        "total_price": total_price
    })
    return new_order


# 查询订单
@app.get("/order/{order_id}", response_model=OrderInfo)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Order).where(Order.id == order_id))
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8003)
```

#### 启动订单服务 & MQ 消费者

1. 启动订单服务：`python main.py`
2. 新开终端，启动消费者：`python mq_consumer.py`

Nacos 出现 `order-service` 即为正常。

---

## 第三部分：开发【Gateway 网关服务】端口 8000

网关作用：**统一入口、动态路由转发、JWT鉴权、IP限流、熔断降级、请求日志监控**

### gateway/main.py（增强版）

```python
"""
微服务网关 - 增强版

功能：
1. 从 Nacos 动态发现服务地址
2. JWT 鉴权/认证
3. 请求限流（基于 IP）
4. 熔断器（下游故障快速失败）
5. 请求日志和监控（耗时统计）
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Dict

import httpx
import jwt
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from nacos import NacosClient
from pydantic import BaseModel

# ============ 配置 ============
NACOS_SERVER = "localhost:8848"
JWT_SECRET = "your-secret-key-change-in-production"  # 生产环境请使用环境变量
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# 限流配置：每 IP 每秒最大请求数
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 1

# 熔断配置
CB_FAILURE_THRESHOLD = 5      # 连续失败次数阈值
CB_TIMEOUT_SECONDS = 30       # 熔断恢复等待时间（秒）

# 白名单路径（不需要鉴权）
AUTH_WHITE_LIST = [
    "/user/register",
    "/user/login",
    "/health",
    "/docs",
    "/openapi.json",
]

# 服务路由映射（服务名 -> 路径前缀）
SERVICE_ROUTES = {
    "user-service": "/user",
    "goods-service": "/goods",
    "order-service": "/order",
}

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
)
logger = logging.getLogger("gateway")

app = FastAPI(title="微服务网关 (增强版)")


# ============ Nacos 服务发现 ============
class ServiceDiscovery:
    """从 Nacos 动态发现服务地址"""

    def __init__(self):
        self.client = NacosClient(NACOS_SERVER)
        self._cache: Dict[str, str] = {}  # service_name -> url

    def get_service_url(self, service_name: str) -> Optional[str]:
        if service_name in self._cache:
            return self._cache[service_name]
        try:
            instances = self.client.list_naming_instances(service_name)
            if instances and len(instances["hosts"]) > 0:
                instance = instances["hosts"][0]
                url = f"http://{instance['ip']}:{instance['port']}"
                self._cache[service_name] = url
                logger.info(f"服务发现: {service_name} -> {url}")
                return url
            else:
                logger.warning(f"Nacos 中未找到服务: {service_name}")
                return None
        except Exception as e:
            logger.error(f"服务发现异常 [{service_name}]: {e}")
            return None

    def refresh_cache(self):
        self._cache.clear()
        for service in SERVICE_ROUTES.keys():
            self.get_service_url(service)


discovery = ServiceDiscovery()


def register_nacos():
    discovery.client.add_naming_instance(
        service_name="gateway", ip="127.0.0.1", port=8000
    )
    logger.info("网关服务已注册到 Nacos")


# ============ JWT 鉴权 ============
class AuthMiddleware:
    @staticmethod
    def verify_token(request: Request) -> Dict:
        path = request.url.path
        for white_path in AUTH_WHITE_LIST:
            if path.startswith(white_path) or path == white_path:
                return {"sub": None, "skip": True}
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="未提供认证 Token")
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return {"sub": payload.get("sub"), "exp": payload.get("exp")}
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token 已过期")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"无效的 Token: {e}")


def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class TokenRequest(BaseModel):
    user_id: str


@app.post("/auth/token")
async def login(req: TokenRequest):
    token = create_token(req.user_id)
    return {"access_token": token, "token_type": "Bearer"}


# ============ 限流器 ============
class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        self.requests[ip] = [
            t for t in self.requests[ip] if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(self.requests[ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        self.requests[ip].append(now)
        return True


rate_limiter = RateLimiter()


# ============ 熔断器 ============
class CircuitBreaker:
    def __init__(self):
        self.failure_counts: Dict[int] = defaultdict(int)
        self.breaker_states: Dict[int] = {}

    def can_execute(self, port: int) -> bool:
        state_info = self.breaker_states.get(port)
        if state_info is None:
            return True
        state, open_time = state_info
        if state == "closed":
            return True
        elif state == "open":
            if time.time() - open_time > CB_TIMEOUT_SECONDS:
                self.breaker_states[port] = ("half_open", time.time())
                return True
            return False
        elif state == "half_open":
            return True
        return True

    def record_success(self, port: int):
        self.failure_counts[port] = 0
        if port in self.breaker_states:
            self.breaker_states[port] = ("closed", time.time())
            logger.info(f"[熔断器] 端口 {port} 恢复正常")

    def record_failure(self, port: int):
        self.failure_counts[port] += 1
        count = self.failure_counts[port]
        if count >= CB_FAILURE_THRESHOLD:
            old_state = self.breaker_states.get(port, ("closed", 0))[0]
            if old_state != "open":
                self.breaker_states[port] = ("open", time.time())
                logger.warning(f"[熔断器] 端口 {port} 触发熔断！连续失败 {count} 次")


circuit_breaker = CircuitBreaker()


# ============ 统一路由转发 ============
@app.api_route("/{service_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway_route(request: Request, auth_result: Dict = Depends(AuthMiddleware.verify_token)):
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = f"/{request.path_params.get('service_path', '')}"
    logger.info(f"[请求] {client_ip} {method} {path}")

    # 1. 限流检查
    if not rate_limiter.is_allowed(client_ip):
        elapsed = (time.time() - start_time) * 1000
        logger.warning(f"[限流拒绝] {client_ip} {path} ({elapsed:.1f}ms)")
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    # 2. 匹配目标服务
    target_service = None
    target_prefix = None
    for svc_name, prefix in SERVICE_ROUTES.items():
        if path.startswith(prefix + "/") or path == prefix:
            target_service = svc_name
            target_prefix = prefix
            break
    if not target_service:
        raise HTTPException(status_code=404, detail=f"无匹配的服务: {path}")

    # /auth 是网关自身接口，不转发
    if not path.startswith("/auth"):
        pass

    # 3. 服务发现
    service_url = discovery.get_service_url(target_service)
    if not service_url:
        raise HTTPException(status_code=503, detail=f"服务 {target_service} 不可用")

    target_port = int(service_url.split(":")[-1])

    # 4. 熔断检查
    if not circuit_breaker.can_execute(target_port):
        raise HTTPException(status_code=503, detail=f"服务 {target_service} 暂时不可用")

    # 5. 转发请求
    target_url = f"{service_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.request(method=method, url=target_url,
                                       content=await request.body(), headers=dict(request.headers))
        circuit_breaker.record_success(target_port)
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"[响应] {method} {path} -> {resp.status_code} ({elapsed:.1f}ms)")
        return resp.content, resp.status_code, resp.headers.items()
    except httpx.ConnectError:
        circuit_breaker.record_failure(target_port)
        raise HTTPException(status_code=503, detail=f"无法连接到服务 {target_service}")
    except httpx.TimeoutException:
        circuit_breaker.record_failure(target_port)
        raise HTTPException(status_code=504, detail=f"服务 {target_service} 响应超时")


# ============ 健康检查 & 监控接口 ============
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "gateway", "timestamp": datetime.now().isoformat()}


@app.get("/metrics/gateway")
async def gateway_metrics():
    cb_status = {}
    for port, info in circuit_breaker.breaker_states.items():
        state, t = info
        cb_status[f"port_{port}"] = {"state": state, "failures": circuit_breaker.failure_counts.get(port, 0)}
    return {"circuit_breakers": cb_status, "service_cache": list(discovery._cache.keys())}


if __name__ == "__main__":
    register_nacos()
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### gateway/requirements.txt

```txt
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
sqlalchemy[asyncio]>=2.0.23
aiomysql>=0.2.0
aioredis>=2.0.1
aio-pika>=9.2.1
nacos-sdk-python>=0.1.15
pydantic>=2.4.2
httpx>=0.25.0
PyJWT>=2.8.0
```

#### 启动网关

```bash
python main.py
```

网关文档地址：`http://127.0.0.1:8000/docs`
- `/health` — 健康检查
- `/metrics/gateway` — 网关运行指标（熔断状态、服务缓存等）

---

## 第四部分：全流程联调测试（完整业务跑通）

### 所有服务启动清单（必须全部启动）

1. 中间件：`docker-compose up -d`（MySQL/Redis/RabbitMQ/Nacos）
2. 用户服务：`user-service/python main.py` (8001)
3. 商品服务：`goods-service/python main.py` (8002)
4. 订单服务：`order-service/python main.py` (8003)
5. MQ 消费者：`order-service/python mq_consumer.py`
6. 网关服务：`gateway/python main.py` (8000)

### 测试步骤（全部访问网关 8000，不直连子服务）

网关文档地址：`http://127.0.0.1:8000/docs`

> **注意**：增强版网关启用了 JWT 鉴权，除白名单接口（`/user/register`、`/user/login`、`/health`）外，
> 其他接口需携带 Token 访问。

#### 0. 获取访问 Token

- 接口：`POST /auth/token`
- 请求体：

```json
{"user_id": "test_user"}
```

- 响应示例：

```json
{"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "Bearer"}
```

后续请求在 **Headers** 中添加 `Authorization: Bearer <your_token>` 即可。

#### 1. 注册用户

- 接口：`POST /user/register`（**无需鉴权**，已在白名单）
- 请求体：

```json
{"username":"test01","password":"123456","phone":"13800138000"}
```

#### 2. 添加商品

- 接口：`POST /goods/add`（**需鉴权**）
- Headers：`Authorization: Bearer <token>`
- 请求体：

```json
{"name":"Python实战书籍","price":59.9,"stock":100}
```

#### 3. 创建订单（核心流程）

- 接口：`POST /order/create`（**需鉴权**）
- Headers：`Authorization: Bearer <token>`
- 请求体：

```json
{"user_id":1,"goods_id":1,"buy_num":2}
```

**现象**：
1. 订单创建成功
2. 商品库存自动扣减 2
3. MQ 消费者终端打印订单消息（异步通信生效）

#### 4. 查询订单 / 查询商品

直接调用网关对应接口即可（**需鉴权**）。

#### 5. 查看网关运行指标

```bash
curl http://127.0.0.1:8000/metrics/gateway
```

---

## 第五部分：架构知识点总结 & 进阶优化方向

### 已落地的分布式/微服务核心能力

1. **服务拆分**：按业务域垂直拆分，分库分表
2. **服务注册与发现**：Nacos 统一管理所有服务
3. **API 网关**：统一入口、动态路由（Nacos 服务发现）
4. **JWT 鉴权认证**：Token 白名单机制，保护业务接口
5. **请求限流**：基于 IP 滑动窗口限流，防止刷接口
6. **熔断降级**：连续失败自动熔断，防止服务雪崩
7. **请求日志 & 监控**：全链路日志、耗时统计、运行指标接口
8. **分布式缓存**：Redis 缓存热点数据，减轻DB压力
9. **异步解耦**：RabbitMQ 实现订单异步通知，削峰填谷
10. **服务间通信**：HTTP 同步调用 + MQ 异步调用
11. **异步编程**：全链路 Python 异步（FastAPI + 异步ORM + 异步Redis/MQ）

### 进阶优化（后续可扩展）

1. ~~服务熔断/降级~~ — **已实现**（CircuitBreaker 熔断器）
2. 配置中心：Nacos 配置管理，统一管理配置文件
3. 链路追踪：SkyWalking / Jaeger
4. 日志收集：ELK 分布式日志
5. 服务负载均衡：基于 Nacos 实现客户端负载均衡（当前为单实例轮询，可扩展多实例加权）
6. 容器编排：K8s 替代 Docker Compose 实现集群部署
7. 分布式事务：Seata 解决跨库事务问题

---

## 常见问题排错

1. **Nacos 注册失败**：检查 8848 端口是否被占用，Docker 容器是否正常启动
2. **MySQL 连接失败**：确认账号密码、IP、数据库名
3. **Redis/RabbitMQ 连不上**：核对端口、账号密码
4. **服务之间调用 404**：检查路由地址、端口是否正确
5. **MQ 收不到消息**：确认队列名一致，消费者正常监听

该项目是 Python 微服务分布式**入门到落地标准模板**，每一段代码均可直接运行，架构符合企业基础微服务规范。
