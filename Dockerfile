# 基础镜像：Python3.11 + Ubuntu 22.04 slim（ARM64原生兼容）
FROM python:3.11-slim-bookworm

WORKDIR /app

# ========== 1. 安装系统依赖（含Torch/ONNX运行依赖） ==========
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    nodejs \
    npm \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    libgomp1 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# ========== 2. 升级pip + 配置双源（优先官方Torch源） ==========
# 升级pip解决ARM64依赖解析问题
RUN pip install --upgrade pip && \
    # 清华源加速普通包，Torch用官方源
    pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple && \
    npm config set registry https://registry.npmmirror.com

# ========== 3. 安装Torch/Torchaudio（核心修复：去掉+cpu后缀，适配ARM64） ==========
# ARM64架构下，Torch CPU版直接用纯版本号，无+cpu后缀
RUN pip install --no-cache-dir \
    torch==2.3.1 \
    torchaudio==2.3.1 \
    # 优先从Torch官方源拉取ARM64预编译包（关键）
    -f https://download.pytorch.org/whl/cpu \
    # 强制不使用CUDA，确保装CPU版
    --no-cache-dir \
    --force-reinstall

# ========== 4. 复制依赖文件 ==========
COPY requirements.txt package.json ./

# ========== 5. 拆分安装依赖（避免冲突） ==========
# 基础Python库
RUN pip install --no-cache-dir \
    qrcode[pil] \
    numpy>=1.23.0 \
    pandas>=2.0.0 \
    openpyxl \
    python-dateutil \
    pytz \
    beautifulsoup4 \
    lxml \
    pyyaml \
    redis \
    pymysql \
    psycopg2-binary \
    jieba>=0.42.1 \
    && rm -rf /root/.cache/pip


# 安装requirements.txt剩余依赖
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

# ========== 6. Node.js依赖 ==========
RUN npm install --production && \
    npm cache clean --force && \
    rm -rf /root/.npm

# ========== 7. 复制代码 + 创建目录 ==========
COPY src/ app.py scripts_repo/ static/ templates/ ./

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

# ========== 8. 暴露端口 + 健康检查 + 启动 ==========
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]