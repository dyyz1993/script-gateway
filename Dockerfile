# 替换为原生支持arm64的Python Alpine镜像，手动安装Node.js
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# ========== 核心修复：补全apk add的续行符，避免语法错误 ==========
# 所有apk add的参数必须用\换行，确保在同一个RUN指令内
RUN apk add --no-cache \
    curl \
    ffmpeg \
    nodejs \
    npm \
    # Python库编译依赖（每行末尾加\，最后一行不加）
    gcc \
    musl-dev \
    postgresql-dev \  # 适配psycopg2-binary
    libxml2-dev \     # 适配lxml
    libxslt-dev \
    python3-dev \
    # 清理apk缓存
    && rm -rf /var/cache/apk/*

# ========== 配置国内镜像源 ==========
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple && \
    npm config set registry https://registry.npmmirror.com

# ========== 复制依赖文件 ==========
COPY requirements.txt package.json ./

# ========== 安装Python依赖 + 清理缓存 ==========
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
    && rm -rf /root/.cache/pip

# ========== 安装Node.js依赖 + 清理缓存 ==========
RUN npm install --production \
    && npm cache clean --force \
    && rm -rf /root/.npm

# ========== 复制应用代码（合并+去重） ==========
COPY src/ app.py scripts_repo/ static/ templates/ ./

# ========== 创建必要目录 ==========
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

# ========== 暴露端口 + 健康检查 + 启动命令 ==========
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]