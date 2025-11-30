# 原生支持arm64的Python Alpine镜像
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 安装系统依赖（补充torch运行的必要依赖）
RUN apk add --no-cache \
    curl \
    ffmpeg \
    nodejs \
    npm \
    # torch编译/运行依赖
    gcc \
    musl-dev \
    libstdc++ \
    gcompat \
    # 其他Python库编译依赖
    postgresql-dev \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    && rm -rf /var/cache/apk/*

# 配置国内镜像源
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple && \
    npm config set registry https://registry.npmmirror.com

# ========== 核心修复：先安装torch/torchaudio（指定arm64 CPU版） ==========
# 从PyTorch官方源安装arm64 CPU版，避免PyPI源无适配包的问题
RUN pip install --no-cache-dir \
    torch==2.4.0+cpu \
    torchaudio==2.4.0+cpu \
    -f https://download.pytorch.org/whl/cpu/torch_stable.html

# 复制依赖文件
COPY requirements.txt package.json ./

# ========== 安装其他Python依赖（排除已手动装的torch/torchaudio） ==========
RUN pip install --no-cache-dir -r requirements.txt \
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
    psycopg2-binary \
    # 单独装modelscope（适配Python 3.11）
    modelscope>=1.15.0 \
    funasr>=1.0.0 \
    onnxruntime-cpu>=1.15.0 \
    jieba>=0.42.1 \
    && rm -rf /root/.cache/pip

# 安装Node.js依赖 + 清理缓存
RUN npm install --production \
    && npm cache clean --force \
    && rm -rf /root/.npm

# 复制应用代码
COPY src/ app.py scripts_repo/ static/ templates/ ./

# 创建必要目录
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