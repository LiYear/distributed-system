# ============================================
# Dockerfile — 4 个微服务共用
# 用途：docker-compose.yml 通过 command 覆盖启动目录和端口
# ============================================

FROM python:3.11-slim

WORKDIR /app

# 替换 apt 源为阿里云国内源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装 vim（方便进容器调试）
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    && rm -rf /var/lib/apt/lists/*


# 先复制依赖文件（利用 Docker 缓存层）
COPY requirements.txt .

# 安装依赖 + 升级 pip（verbose 输出，方便排查）
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制整个项目代码
COPY . .

# 默认暴露端口（运行时通过 docker-compose ports 覆盖）
EXPOSE 8000

# 默认启动命令（docker-compose.yml 中每个服务会覆盖 command）
# 临时：保持容器运行不退出，方便手动进容器调试
CMD ["tail", "-f", "/dev/null"]
