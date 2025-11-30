# 使用同时包含 Python 和 Node.js 的官方镜像
FROM nikolaik/python-nodejs:python3.11-nodejs20

# 设置工作目录
WORKDIR /app

# 安装必要的系统工具(curl 用于健康检查, ffmpeg 用于音视频处理)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 国内镜像源
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

# 配置 npm 国内镜像源
RUN npm config set registry https://registry.npmmirror.com

# 复制依赖文件
COPY requirements.txt package.json ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 预装常见的 Python 库（可选，根据实际需求添加）
RUN pip install --no-cache-dir \
    qrcode[pil] \
    numpy \
    pandas \
    openpyxl \
    python-dateutil \
    pytz \
    beautifulsoup4 \
    lxml \
    pyyaml \
    redis \
    pymysql \
    psycopg2-binary

# 安装 Node.js 依赖
RUN npm install --production

# 复制应用代码（只复制必要的文件）
COPY src/ ./src/
COPY app.py ./
COPY requirements.txt ./
COPY package.json ./
COPY scripts_repo/ ./scripts_repo/
COPY static/ ./static/
COPY templates/ ./templates/

# 创建必要的目录（使用实际的目录结构）
RUN mkdir -p \
    /app/scripts_repo/python \
    /app/scripts_repo/js \
    /app/static \
    /app/templates \
    /app/logs/script \
    /app/logs/gateway \
    /app/tmp \
    /tmp/funasr_cache \
    /root/.cache/modelscope \
    /root/.cache/huggingface

# 暴露端口
EXPOSE 8001

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
