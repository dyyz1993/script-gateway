# 替换为原生支持arm64的Python Alpine镜像，手动安装Node.js（避免第三方镜像架构兼容问题）
FROM python:3.11-alpine

# 设置工作目录（提前设置，减少层数量）
WORKDIR /app

# ========== 核心修复：Alpine系统用apk替代apt-get，安装必要依赖 ==========
# 安装：curl（健康检查）、ffmpeg（音视频处理）、Node.js+npm（满足双环境需求）
# 补充Python库编译依赖（适配psycopg2、lxml等库）
RUN apk add --no-cache \
    curl \
    ffmpeg \
    nodejs \
    npm \
    # Python库编译依赖（按需保留，安装后不删除，部分库运行时也需要）
    gcc \
    musl-dev \
    postgresql-dev \  # 适配psycopg2-binary
    libxml2-dev \     # 适配lxml
    libxslt-dev \
    python3-dev \
    # 清理apk缓存，减少体积
    && rm -rf /var/cache/apk/*

# ========== 配置国内镜像源，加速依赖安装 ==========
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple && \
    npm config set registry https://registry.npmmirror.com

# ========== 复制依赖文件（仅复制必要的，减少上下文） ==========
COPY requirements.txt package.json ./

# ========== 安装Python依赖，清理缓存 ==========
RUN pip install --no-cache-dir -r requirements.txt \
    # 预装常用库，合并安装减少层
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
    # 清理pip缓存，减少镜像体积
    && rm -rf /root/.cache/pip

# ========== 安装Node.js依赖，清理缓存 ==========
RUN npm install --production \
    # 清理npm缓存
    && npm cache clean --force \
    && rm -rf /root/.npm

# ========== 优化COPY：合并所有代码复制，删除重复操作 ==========
# 去掉重复的requirements.txt/package.json复制（已提前复制过）
COPY src/ app.py scripts_repo/ static/ templates/ ./

# ========== 创建必要目录，保持原有目录结构 ==========
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

# ========== 暴露端口 + 健康检查 + 启动命令（保持原有逻辑） ==========
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]