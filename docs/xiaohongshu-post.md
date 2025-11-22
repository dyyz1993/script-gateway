# 🚀 解决 n8n 脚本依赖难题！ScriptGateway 让自动化更简单

## 💡 你是否遇到过这些问题？

用 n8n 做自动化流程时：
- ❌ 内置代码节点无法安装第三方库（playwright、pandas...）
- ❌ 想用爬虫采集数据，但 n8n 环境不支持
- ❌ 脚本调试麻烦，每次都要在工作流里测试
- ❌ 依赖管理混乱，版本冲突难以解决

## ✨ ScriptGateway 来帮你！

一个专为 n8n 设计的脚本网关平台，3 分钟让你的脚本变成 API！

### 🎯 核心功能

**📦 智能依赖管理**
- Web 界面一键安装 Python/Node.js 依赖
- 自动检测依赖冲突
- 支持 Playwright、Puppeteer 等爬虫库

**🔄 自动 API 注册**
- 把脚本丢进文件夹，自动变成 REST API
- 无需写路由代码，专注业务逻辑
- 支持文件上传、JSON 参数

**🐞 可视化调试**
- Web 表单在线调试脚本
- 实时查看输出和错误
- 执行历史和日志追踪

**🐳 开箱即用**
- Docker 一键部署
- 预装常用依赖（pandas、numpy、qrcode...）
- 国内镜像加速

## 📸 界面预览

[上传你的截图]
- 脚本管理界面：一目了然的状态和调用统计
- 依赖管理：可视化安装和管理
- 在线调试：表单填参数，实时看结果

## 🌟 实战场景

### 场景 1：n8n + 爬虫数据采集

**传统方式**：
n8n 内置代码节点 → ❌ 无法安装 playwright

**用 ScriptGateway**：
1. 在 ScriptGateway 安装 playwright
2. 写爬虫脚本（自动注册为 API）
3. n8n HTTP 节点调用 API → ✅ 获取数据
4. n8n 处理数据（筛选、存储...）

### 场景 2：复杂数据处理

需要 pandas、numpy 等科学计算库？
- ScriptGateway 提供完整 Python 环境
- 一键安装依赖
- n8n 通过 HTTP 调用即可

### 场景 3：定时任务通知

- 脚本执行自动 Webhook 通知
- 失败自动告警
- 日志集中管理

## 🚀 快速开始

```bash
# 1. 拉取项目
git clone https://github.com/dyyz1993/script-gateway.git
cd script-gateway

# 2. 启动服务
docker-compose up -d

# 3. 访问管理界面
# http://localhost:8001
```

3 分钟搞定！

## 💪 技术栈

- Python 3.11 + FastAPI
- Node.js 20
- SQLite
- Docker

## 📝 示例脚本

```python
import argparse
import json
from playwright.sync_api import sync_playwright

# 定义参数
ARGS_MAP = {
    "url": {"flag": "--url", "type": "str", "required": True, "help": "目标URL"}
}

def main():
    # ScriptGateway 自动解析参数
    args = parse_args()
    
    # 使用 Playwright 爬取
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(args.url)
        title = page.title()
        browser.close()
    
    # 返回 JSON
    print(json.dumps({"title": title}))
```

在 n8n 中调用：
```
POST http://script-gateway:8001/api/scripts/1/run
Body: {"url": "https://example.com"}
```

## 🎁 项目特点

✅ 零学习成本：会写 Python/JS 就能用
✅ 完整文档：中英文 README + Swagger API
✅ 开箱即用：Docker 一键启动
✅ 活跃维护：欢迎 Issue 和 PR

## 🔗 项目地址

GitHub：https://github.com/dyyz1993/script-gateway

⭐ 觉得有用的话，给个 Star 支持一下！

## 🏷️ 标签

#n8n #自动化 #爬虫 #API #Docker #Python #JavaScript #工作流 #效率工具 #开源项目

---

**评论区互动**：
💬 你在用 n8n 时遇到过什么痛点？
💬 还希望 ScriptGateway 支持哪些功能？
💬 分享你的自动化场景！

---

**关注我**，持续分享：
✨ 自动化工作流技巧
✨ 开源工具推荐
✨ Python/JS 实战案例
