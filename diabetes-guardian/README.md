# 糖尿病智能监护系统 (Diabetes Guardian)

基于 FastAPI + LangGraph + Celery 的实时糖尿病监护 Agent 系统。

## 快速开始

### 前置要求

- Python 3.11+
- MySQL 8.0+
- Redis 7+
- uv (Python 虚拟环境管理)

### 安装

```bash
# 创建并激活虚拟环境
uv venv
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt

# 复制并编辑环境变量
cp .env.example .env
# 编辑 .env 填入你的配置

# 初始化数据库
mysql -u guardian -p diabetes_guardian < db/init.sql
```

### 启动服务

每个服务需要单独开一个终端，先激活虚拟环境 `source .venv/bin/activate`：

```bash
# 终端 1: Patient History MCP Server
uvicorn mcp_servers.patient_history_mcp:app --host 127.0.0.1 --port 8001 --reload

# 终端 2: Location Context MCP Server
uvicorn mcp_servers.location_context_mcp:app --host 127.0.0.1 --port 8002 --reload

# 终端 3: Celery Worker
celery -A agent.main worker --loglevel=info

# 终端 4: Gateway API
uvicorn gateway.main:app --host 127.0.0.1 --port 8000 --reload
```

### 测试

```bash
# 发送测试遥测数据
curl -X POST http://127.0.0.1:8000/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "timestamp": "2024-06-15T13:30:00",
    "heart_rate": 75,
    "glucose": 4.8,
    "gps_lat": 39.9042,
    "gps_lng": 116.4074
  }'

# 运行单元测试
pytest tests/ -v
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| Agent 编排 | LangGraph |
| 任务队列 | Celery + Redis |
| 数据库 | MySQL (SQLAlchemy 2.0 async) |
| LLM | Gemini 2.0 Pro (langchain-google-genai) |
| 日志 | structlog |

## 项目结构

```
diabetes-guardian/
├── gateway/          # 流处理与规则网关层
├── agent/            # 认知与调度层（LangGraph）
├── mcp_servers/      # 基建层 MCP Servers
├── db/               # 数据库 Schema 与 ORM
└── tests/            # 测试
```
