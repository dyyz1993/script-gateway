# 基础镜像：Python3.11 + Ubuntu 22.04 slim（glibc，兼容torch官方预编译包）
# 原生支持linux/arm64、linux/amd64，无需跨架构模拟
FROM python:3.11-slim-bookworm

# 设置工作目录（固定层，减少缓存失效）
WORKDIR /app

# ========== 1. 安装系统级依赖（适配arm64，精简版） ==========
# 包含：curl（健康检查）、ffmpeg（音视频）、Node.js+npm（双环境）、编译依赖（适配Python库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    nodejs \
    npm \
    # Python库编译依赖（按需安装，避免冗余）
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    # 清理apt缓存（减少镜像体积，关键步骤）
    && rm -rf /var/lib/apt/lists/*

# ========== 2. 配置国内镜像源（加速依赖安装） ==========
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple && \
    # npm 国内源（淘宝镜像）
    npm config set registry https://registry.npmmirror.com

# ========== 3. 优先安装 torch/torchaudio（解决架构兼容问题） ==========
# 选择官方源存在的最新CPU版（2.3.1+cpu），满足>=2.0.0的要求
RUN pip install --no-cache-dir \
    torch==2.3.1+cpu \
    torchaudio==2.3.1+cpu \
    # 指定torch官方whl源，避免PyPI源适配问题
    -f https://download.pytorch.org/whl/cpu/torch_stable.html

# ========== 4. 复制依赖文件（仅复制必要文件，减少构建上下文） ==========
COPY requirements.txt package.json ./

# ========== 5. 安装剩余Python依赖（清理缓存，减少体积） ==========
RUN pip install --no-cache-dir -r requirements.txt \
    # 预装常用库（合并安装，减少镜像层）
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
    # SenseVoiceSmall 相关依赖（补充）
    modelscope>=1.15.0 \
    funasr>=1.0.0 \
    onnxruntime-cpu>=1.15.0 \
    jieba>=0.42.1 \
    # 清理pip缓存（减少镜像体积约100MB）
    && rm -rf /root/.cache/pip

# ========== 6. 安装Node.js依赖（生产环境，清理缓存） ==========
RUN npm install --production && \
    npm cache clean --force && \
    rm -rf /root/.npm

# ========== 7. 复制应用代码（合并COPY，减少层数量） ==========
COPY src/ app.py scripts_repo/ static/ templates/ ./

# ========== 8. 创建必要目录（匹配业务逻辑） ==========
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

# ========== 9. 暴露端口 + 健康检查 + 启动命令 ==========
# 暴露应用端口
EXPOSE 8001

# 健康检查（确保服务存活）
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# 启动命令（uvicorn运行FastAPI）
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]