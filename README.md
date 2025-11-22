# ScriptGateway - 脚本网关

[English](./README_EN.md) | 简体中文

## 📖 项目简介

ScriptGateway（脚本网关）是一个轻量级的脚本托管与 API 网关平台，专为与 n8n、Zapier 等工作流自动化工具配合使用而设计。它通过 Docker 容器化部署，快速将 Python 和 JavaScript 脚本转换为 RESTful API 接口，解决了 n8n 内置代码节点的依赖管理难题。

### 🎯 核心价值

- **解决依赖问题**：n8n 内置脚本节点无法安装第三方依赖，ScriptGateway 提供独立的依赖管理环境
- **快速暴露 API**：脚本自动注册为 HTTP 接口，无需编写路由代码
- **爬虫集成**：内置 Playwright/Puppeteer 支持，轻松为 n8n 提供爬虫数据采集能力
- **可视化管理**：Web 界面管理脚本、依赖、日志，调试更便捷

---

## ✨ 核心特性

### 🚀 自动化脚本注册
- 📁 自动扫描 `scripts_repo/` 目录，将 Python/JS 脚本转换为 API
- 🔄 文件变更时自动热重载
- 📝 基于脚本注释自动生成 Swagger API 文档
- 🎨 支持文件上传、JSON 参数、GET/POST 请求

### 📦 依赖管理
- 🐍 Python 依赖：通过 Web 界面安装 pip 包
- 📦 Node.js 依赖：通过 Web 界面安装 npm 包
- 🔍 依赖冲突检测与解决
- 💾 依赖配置持久化到 `requirements.txt` / `package.json`

### 🎛️ Web 管理界面
- 📊 脚本列表：查看脚本状态、调用次数、执行历史
- 🐞 在线调试：Web 表单调试脚本，实时查看输出
- 📝 脚本编辑：在线编辑脚本代码
- 📜 日志查看：查看脚本执行日志和历史记录
- 🔔 通知配置：Webhook 通知脚本执行结果

### 🐳 Docker 部署
- 一键启动，预装常用依赖（qrcode、pandas、numpy、playwright 等）
- 国内镜像源加速（清华源、npmmirror）
- 目录映射支持外部修改脚本和配置

---

## 📸 界面预览

### 脚本管理主界面
![脚本管理](docs/screenshots/main.png)

展示所有脚本的状态、调用次数、上次执行时间等信息，支持搜索、批量删除。

### 依赖管理界面
![依赖管理](docs/screenshots/deps.png)

可视化管理 Python 和 Node.js 依赖，显示安装状态，一键安装配置文件中的依赖。

### 在线调试界面
![在线调试](docs/screenshots/debug.png)

通过表单填写参数，实时执行脚本并查看输出结果。

---

## 🚀 快速开始

### 前置要求

- Docker
- Docker Compose

### 部署步骤

#### 1. 克隆项目

```bash
git clone https://github.com/dyyz1993/script-gateway.git
cd script-gateway
```

#### 2. 启动服务

```bash
docker-compose up -d
```

#### 3. 访问管理界面

打开浏览器访问：http://localhost:8001

### 环境变量配置

在 `docker-compose.yml` 中可以配置以下参数：

```yaml
environment:
  - SCAN_INTERVAL_SEC=5       # 脚本扫描间隔（秒）
  - TIMEOUT_MIN=10            # 脚本执行超时时间（分钟）
  - NOTIFY_URL=               # Webhook 通知地址
```

---

## 📝 使用指南

### 创建第一个脚本

#### 方法 1：通过 Web 界面创建

1. 访问管理界面，点击"新建脚本"
2. 选择"粘贴内容"
3. 输入以下示例代码：

**Python 示例**：
```python
import argparse
import json
import sys

ARGS_MAP = {
    "name": {"flag": "--name", "type": "str", "required": True, "help": "姓名"},
    "age": {"flag": "--age", "type": "str", "required": False, "help": "年龄"}
}

def get_schema():
    return json.dumps(ARGS_MAP, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser()
    for key, cfg in ARGS_MAP.items():
        parser.add_argument(cfg["flag"], required=cfg.get("required", False), help=cfg.get("help", ""))
    
    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)
    
    args = parser.parse_args()
    name = getattr(args, 'name', 'Guest')
    age = getattr(args, 'age', 'unknown')
    
    result = {
        "message": f"Hello {name}!",
        "age": age,
        "code": 200
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

4. 点击保存，脚本将自动注册为 API

#### 方法 2：直接放置脚本文件

将脚本文件放入：
- Python: `scripts_repo/python/`
- JavaScript: `scripts_repo/js/`

系统会自动扫描并注册。

### 调用脚本 API

脚本注册后，可通过以下方式调用：

#### 1. 在 n8n 中调用

使用 **HTTP Request** 节点：

```
URL: http://script-gateway:8001/api/scripts/{script_id}/run
Method: POST
Content-Type: application/json

Body:
{
  "name": "Alice",
  "age": "25"
}
```

#### 2. 使用 cURL 调用

```bash
curl -X POST http://localhost:8001/api/scripts/1/run \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "age": "25"}'
```

#### 3. 查看 Swagger 文档

访问：http://localhost:8001/scripts-swagger.html

---

## 🌟 高级功能

### 1. 爬虫脚本示例

利用内置的 Playwright 环境采集网页数据：

**Python + Playwright 示例**：
```python
# 需要先在依赖管理中安装: playwright
import argparse
import json
from playwright.sync_api import sync_playwright

ARGS_MAP = {
    "url": {"flag": "--url", "type": "str", "required": True, "help": "目标URL"}
}

def main():
    # ... 参数解析代码 ...
    
    url = getattr(args, 'url', '')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        title = page.title()
        content = page.content()
        browser.close()
    
    result = {
        "title": title,
        "html_length": len(content),
        "url": url
    }
    print(json.dumps(result, ensure_ascii=False))
```

### 2. 文件上传处理

脚本可以接收文件参数：

```python
ARGS_MAP = {
    "image": {"flag": "--image", "type": "file", "required": True, "help": "图片文件"}
}

# 文件会保存到临时路径，通过 args.image 获取路径
```

### 3. 定时任务通知

启用通知功能后，脚本执行结果会通过 Webhook 发送：

```json
{
  "script_id": 1,
  "script_name": "hello.py",
  "status": "success",
  "output": "执行结果...",
  "duration_ms": 1250
}
```

---

## 🔧 目录结构

```
script-gateway/
├── app.py                  # 主应用入口
├── config.py               # 配置文件
├── database.py             # 数据库操作
├── scanner.py              # 脚本扫描器
├── executor.py             # 脚本执行器
├── deps.py                 # 依赖管理
├── logger.py               # 日志管理
├── static/                 # 前端页面
│   ├── index.html          # 脚本管理页面
│   ├── deps.html           # 依赖管理页面
│   └── settings.html       # 系统设置页面
├── scripts_repo/           # 脚本存储目录
│   ├── python/             # Python 脚本
│   └── js/                 # JavaScript 脚本
├── templates/              # 脚本模板
├── logs/                   # 日志文件
├── requirements.txt        # Python 依赖
├── package.json            # Node.js 依赖
├── Dockerfile              # Docker 镜像
└── docker-compose.yml      # Docker 编排
```

---

## 🛠️ 技术栈

- **后端**：Python 3.11 + FastAPI + SQLite
- **前端**：原生 HTML/CSS/JavaScript
- **运行时**：Python 3.11 + Node.js 20
- **容器化**：Docker + Docker Compose

---

## 🤝 与 n8n 集成示例

### 场景：抓取网页数据并处理

1. **ScriptGateway**：部署爬虫脚本
2. **n8n**：创建工作流
   - HTTP Request 节点调用 ScriptGateway API
   - 获取爬虫数据
   - 通过 n8n 节点处理数据（筛选、转换、存储）

**优势**：
- ✅ 爬虫依赖（Playwright）在 ScriptGateway 中管理，n8n 无需安装
- ✅ 脚本可独立调试和更新
- ✅ 日志集中管理

---

## 📄 许可证

MIT License

---

## 🙏 致谢

感谢所有为开源社区做出贡献的开发者！

---

## 📞 联系方式

- GitHub Issues: [提交问题](https://github.com/dyyz1993/script-gateway/issues)

---

**⭐ 如果这个项目对您有帮助，请给个 Star！**
