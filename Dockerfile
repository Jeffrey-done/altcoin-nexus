FROM python:3.11-slim as base

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 nexus && chown -R nexus:nexus /app
USER nexus

# 基础镜像阶段
FROM base as core

# 启动核心服务
CMD ["python", "main.py"]

# API 服务阶段
FROM base as api

# 暴露端口
EXPOSE 8000

# 启动 API 服务
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
