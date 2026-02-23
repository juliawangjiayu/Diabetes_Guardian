# 糖尿病智能监护系统 — 完整工程开发文档
> 环境：本地开发 | Python 虚拟环境（uv）| MySQL + Redis 本地安装

---

## 0. 项目目录结构

```
diabetes-guardian/
├── .env                            # 本地环境变量（不提交 git）
├── .env.example                    # 模板，提交 git
├── .gitignore
├── requirements.txt
├── README.md
│
├── gateway/                        # 流处理与规则网关层
│   ├── main.py                     # FastAPI 入口
│   ├── routers/
│   │   └── telemetry.py            # POST /telemetry 端点
│   ├── services/
│   │   ├── triage.py               # 硬触发 & 软触发逻辑
│   │   ├── persistence.py          # 写入 MySQL
│   │   └── notification.py         # 发送推送通知（FCM/APNs）
│   └── schemas.py                  # Pydantic 数据模型
│
├── agent/                          # 认知与调度层（LangGraph）
│   ├── main.py                     # Celery Worker 入口
│   ├── graph.py                    # LangGraph StateGraph 定义
│   ├── state.py                    # AgentState TypedDict
│   └── nodes/
│       ├── investigator.py         # Node 1: 调用 MCP tools
│       ├── reflector.py            # Node 2: LLM 临床推理
│       └── communicator.py         # Node 3: 生成个性化文案并推送
│
├── mcp_servers/                    # 基建层 MCP Servers
│   ├── patient_history_mcp.py      # 封装 MySQL 历史查询（含 NL2SQL）
│   └── location_context_mcp.py     # 经纬度 → 语义位置
│
├── db/
│   ├── init.sql                    # 建表 SQL
│   └── models.py                   # SQLAlchemy ORM 模型
│
└── tests/
    ├── test_triage.py
    ├── test_graph.py
    └── fixtures.py
```

---

## 1. 本地环境准备

### 第一步：安装 MySQL（选择你的系统）

**macOS（推荐 Homebrew）：**
```bash
brew install mysql
brew services start mysql

# 初始化 root 密码
mysql_secure_installation
```

**Ubuntu / Debian：**
```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql
sudo mysql_secure_installation
```

**Windows：**
下载官方安装包：https://dev.mysql.com/downloads/installer/
安装时选 Developer Default，记住 root 密码。

**创建项目数据库和用户：**
```sql
-- 登录 MySQL
mysql -u root -p

-- 执行以下命令
CREATE DATABASE diabetes_guardian CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'guardian'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON diabetes_guardian.* TO 'guardian'@'localhost';
FLUSH PRIVILEGES;
EXIT;

-- 初始化表结构
mysql -u guardian -p diabetes_guardian < db/init.sql
```

---

### 第二步：安装 Redis（选择你的系统）

**macOS：**
```bash
brew install redis
brew services start redis

# 验证是否正常
redis-cli ping
# 返回 PONG 即成功
```

**Ubuntu / Debian：**
```bash
sudo apt install redis-server
sudo systemctl start redis
redis-cli ping
```

**Windows：**
Redis 官方不维护 Windows 版，推荐用 WSL2 运行上面的 Ubuntu 命令，
或下载非官方版本：https://github.com/tporadowski/redis/releases

---

### 第三步：安装 uv 并创建虚拟环境

```bash
# 安装 uv（全局工具，只需一次）
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows PowerShell:
# powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 重启终端后验证
uv --version

# 进入项目目录
cd diabetes-guardian

# 创建虚拟环境（会在项目根目录生成 .venv 文件夹）
uv venv

# 激活虚拟环境
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 安装所有依赖
uv pip install -r requirements.txt

# 验证（应显示 .venv 内的 Python 路径）
which python
```

---

## 2. 依赖清单

```
# requirements.txt

# Web 框架
fastapi==0.111.0
uvicorn[standard]==0.30.1

# 数据验证
pydantic==2.7.1
pydantic-settings==2.3.1

# 数据库
sqlalchemy==2.0.30
aiomysql==0.2.0
pymysql==1.1.1              # 同步操作 / 迁移脚本使用

# 任务队列
celery==5.4.0
redis==5.0.6

# LangGraph & LangChain
langgraph==0.1.19
langchain==0.2.5
langchain-openai==0.1.8     # 如用 OpenAI
# langchain-google-genai==1.0.6  # 如用 Gemini，二选一

# HTTP 客户端（MCP Server 间调用）
httpx==0.27.0

# 日志
structlog==24.2.0

# 工具
python-dotenv==1.0.1
numpy==1.26.4               # 血糖斜率线性回归

# 测试
pytest==8.2.2
pytest-asyncio==0.23.7
pytest-mock==3.14.0
httpx                       # 已上面声明，测试用 AsyncClient
```

---

## 3. 环境变量配置

```bash
# .env.example（复制为 .env 并填入真实值）

# ── 数据库 ──────────────────────────────
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=guardian
MYSQL_PASSWORD=your_password
MYSQL_DB=diabetes_guardian

# ── Redis ───────────────────────────────
REDIS_URL=redis://127.0.0.1:6379/0

# ── LLM（二选一）───────────────────────
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o
# GOOGLE_API_KEY=...
# LLM_MODEL=gemini/gemini-1.5-pro

# ── 推送通知 ────────────────────────────
FCM_SERVER_KEY=your_fcm_server_key

# ── MCP Servers 地址 ────────────────────
PATIENT_HISTORY_MCP_URL=http://127.0.0.1:8001
LOCATION_CONTEXT_MCP_URL=http://127.0.0.1:8002

# ── 安全 ────────────────────────────────
SECRET_KEY=your_random_secret_key_32chars
```

---

## 4. 数据库 Schema

```sql
-- db/init.sql

CREATE TABLE IF NOT EXISTS users (
    user_id       VARCHAR(36) PRIMARY KEY,
    name          VARCHAR(100),
    birth_year    INT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_telemetry_log (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id       VARCHAR(36) NOT NULL,
    recorded_at   DATETIME NOT NULL,
    heart_rate    INT,
    glucose       DECIMAL(5,2),
    gps_lat       DECIMAL(10,7),
    gps_lng       DECIMAL(10,7),
    INDEX idx_user_time (user_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS user_weekly_patterns (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id          VARCHAR(36) NOT NULL,
    day_of_week      TINYINT,        -- 0=Monday ... 6=Sunday
    hour_of_day      TINYINT,        -- 0-23
    activity_type    VARCHAR(50),    -- 'resistance_training', 'cardio', 'rest'
    probability      DECIMAL(4,3),
    avg_glucose_drop DECIMAL(5,2),   -- 该活动平均血糖消耗 mmol/L
    sample_count     INT,
    INDEX idx_user_pattern (user_id, day_of_week, hour_of_day)
);

CREATE TABLE IF NOT EXISTS user_known_places (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      VARCHAR(36) NOT NULL,
    place_name   VARCHAR(100),       -- e.g. "家", "超级健身房"
    place_type   VARCHAR(50),        -- 'home', 'gym', 'office'
    gps_lat      DECIMAL(10,7),
    gps_lng      DECIMAL(10,7),
    INDEX idx_user_places (user_id)
);

CREATE TABLE IF NOT EXISTS intervention_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    triggered_at    DATETIME NOT NULL,
    trigger_type    VARCHAR(50),
    agent_decision  TEXT,            -- Reflector 推理摘要（JSON 字符串）
    message_sent    TEXT,
    user_ack        BOOLEAN DEFAULT FALSE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS error_log (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    service     VARCHAR(50),
    error_msg   TEXT,
    payload     TEXT,
    ts          DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. 数据模型（Pydantic Schemas）

```python
# gateway/schemas.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TelemetryPayload(BaseModel):
    user_id: str
    timestamp: datetime
    heart_rate: int
    glucose: float          # mmol/L
    gps_lat: float
    gps_lng: float

class InvestigationTask(BaseModel):
    """推入 Redis 队列、唤醒 LangGraph Agent 的消息体"""
    user_id: str
    trigger_type: str       # e.g. "SOFT_PRE_EXERCISE_LOW_BUFFER"
    trigger_at: datetime
    current_glucose: float
    current_hr: int
    gps_lat: float
    gps_lng: float
    context_notes: str
```

---

## 6. 网关层（Gateway）

### FastAPI 路由

```
POST /telemetry
  Body: TelemetryPayload
  流程：
    1. 查询 MySQL 获取 user.birth_year
    2. asyncio.gather(
         PersistToMySQL(payload),
         EvaluateTriggers(payload, user_age)
       )
  返回: {"status": "received"}
```

### triage.py 触发逻辑

**`evaluate_hard_triggers(payload, user_age) -> bool`**

满足任一条件即触发：
1. `glucose < 3.9` mmol/L
2. `heart_rate > (220 - user_age) * 0.90`
3. 查询 MySQL，该用户最近 30 分钟内无任何遥测记录（数据中断）

触发后：调用 `NotificationService.send_emergency_alert(user_id, reason)`，返回 True，不唤醒 Agent。

**`evaluate_soft_triggers(payload, user_age) -> Optional[InvestigationTask]`**

滑动窗口：用 `collections.deque`（key=user_id）存最近 20 分钟数据，最大长度 20 条。

满足任一条件触发（且硬触发未命中）：

1. **血糖下降斜率**：对窗口内数据做线性回归（`numpy.polyfit`），斜率 `< -0.1 mmol/L/min`
2. **运动预备低水位**：
   - 查询 `user_weekly_patterns`，当前时间 `±30分钟` 内存在 `probability > 0.70` 的活动
   - 当前血糖在 `[4.0, 5.6]` 区间
   - 距离预测运动开始时间 `< 60分钟`

触发后：`celery_app.send_task('agent.tasks.run_investigation', args=[task.model_dump_json()])`

---

## 7. Agent 层（LangGraph）

### State 定义

```python
# agent/state.py
from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    # 输入
    task: dict
    user_id: str

    # Investigator 填充
    location_context: Optional[str]               # e.g. "距离常去的健身房 500 米"
    glucose_history_24h: Optional[list]
    upcoming_activity: Optional[dict]             # {type, probability, avg_drop}
    recent_exercise_glucose_drops: Optional[List[float]]

    # Reflector 填充
    risk_level: Optional[str]                     # "LOW" | "MEDIUM" | "HIGH"
    reasoning_summary: Optional[str]
    intervention_action: Optional[str]            # "NO_ACTION" | "SOFT_REMIND" | "STRONG_ALERT"

    # Communicator 填充
    message_to_user: Optional[str]
    notification_sent: bool
```

### LangGraph 图结构

```python
# agent/graph.py

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.investigator import investigator_node
from agent.nodes.reflector import reflector_node
from agent.nodes.communicator import communicator_node

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("investigator", investigator_node)
    graph.add_node("reflector", reflector_node)
    graph.add_node("communicator", communicator_node)

    graph.set_entry_point("investigator")
    graph.add_edge("investigator", "reflector")

    # 无风险则结束，不打扰用户
    graph.add_conditional_edges(
        "reflector",
        lambda state: "communicator" if state["intervention_action"] != "NO_ACTION" else END
    )
    graph.add_edge("communicator", END)

    return graph.compile()
```

### Node 1: Investigator

```python
# agent/nodes/investigator.py
# 并发调用两个 MCP Server

async def investigator_node(state: AgentState) -> AgentState:
    task = state["task"]

    location_result, history_result = await asyncio.gather(
        call_location_context_mcp(task["gps_lat"], task["gps_lng"], task["user_id"]),
        call_patient_history_mcp(task["user_id"], task["trigger_at"])
    )

    return {
        **state,
        "location_context": location_result["semantic_location"],
        "glucose_history_24h": history_result["glucose_history_24h"],
        "upcoming_activity": history_result["upcoming_activity"],
        "recent_exercise_glucose_drops": history_result["recent_exercise_drops"]
    }
```

### Node 2: Reflector

```python
# agent/nodes/reflector.py

SYSTEM_PROMPT = """
你是一名专业的糖尿病管理 AI 助手，严格遵循以下指南：
1. 低血糖分级：Level 1 (3.0–3.9), Level 2 (< 3.0), Level 3 (< 2.8 且有症状)
2. 运动前血糖安全区间：5.6–10.0 mmol/L（高强度运动）
3. 你的职责是预防，而非诊断
4. 仅输出以下 JSON，不附加任何其他文字：
   {
     "risk_level": "LOW" | "MEDIUM" | "HIGH",
     "reasoning_summary": "...",
     "intervention_action": "NO_ACTION" | "SOFT_REMIND" | "STRONG_ALERT"
   }
"""

# 实现：构造包含所有 Investigator 数据的 user prompt，
# 调用 LLM，解析返回 JSON，更新 state。
```

### Node 3: Communicator

```python
# agent/nodes/communicator.py

COMMUNICATOR_PROMPT = """
你是用户的健康伴侣。根据以下医学分析，生成一条推送通知。
要求：
- 语气温暖友好，risk_level=HIGH 时才可使用"注意"等词
- 给出 1 个具体可执行的建议（如：吃什么、吃多少克）
- 字数控制在 80 字以内
- 必须提及当前血糖数值
"""

# 实现：生成文案 → NotificationService.send_push(user_id, message)
#       → 写入 intervention_log 表
```

---

## 8. MCP Servers（基建层）

两个独立 FastAPI 进程，通过 HTTP 提供工具接口。

### Patient History MCP（端口 8001）

```
POST /tools/get_patient_context
  Request:  { "user_id": str, "reference_time": str }
  Response: {
    "glucose_history_24h": [{"time": str, "glucose": float}, ...],
    "upcoming_activity": {
        "type": str,
        "probability": float,
        "expected_start_hour": int,
        "avg_glucose_drop": float
    } | null,
    "recent_exercise_drops": [float, float, float]
  }

POST /tools/nl2sql_query
  Request:  { "user_id": str, "natural_language_query": str }
  Response: { "result": any, "sql_executed": str }
  安全限制：SQL 只允许 SELECT，检测到 DROP/UPDATE/DELETE/INSERT 则拒绝执行
```

### Location Context MCP（端口 8002）

```
POST /tools/get_semantic_location
  Request:  { "user_id": str, "lat": float, "lng": float }
  Response: {
    "semantic_location": str,        -- e.g. "在家中" 或 "距离常去的健身房 500 米"
    "is_at_home": bool,
    "nearby_known_places": [
        {"name": str, "distance_m": int, "type": str}
    ]
  }
  实现：查询 user_known_places 表，用 Haversine 公式计算距离，200m 内视为到达
```

---

## 9. 错误处理与降级策略

| 场景 | 降级行为 |
|------|----------|
| MySQL 连接失败 | 硬触发仅用内存缓存判断，软触发跳过，写 error_log |
| MCP Server 超时（> 3s） | Investigator 用默认空值继续流程，打 warning 日志 |
| LLM API 调用失败 | Reflector 规则兜底：血糖 < 4.5 且有运动计划 → SOFT_REMIND |
| Redis 连接失败 | Celery Task 降级为同步执行 `task.apply()` |

所有外部 HTTP 调用规范：
- 使用 `httpx.AsyncClient(timeout=5.0)`
- 最多重试 2 次，指数退避（1s → 2s）
- 失败后写入 `error_log` 表

---

## 10. 本地启动顺序

每个服务需要**单独开一个终端窗口**，按以下顺序启动：

```bash
# 终端 0：确认 MySQL 和 Redis 在后台运行
mysql -u guardian -p -e "SELECT 1"        # 验证 MySQL
redis-cli ping                             # 验证 Redis，返回 PONG

# ── 激活虚拟环境（每个终端都需要执行）──
source .venv/bin/activate

# 终端 1：Patient History MCP Server
uvicorn mcp_servers.patient_history_mcp:app --host 127.0.0.1 --port 8001 --reload

# 终端 2：Location Context MCP Server
uvicorn mcp_servers.location_context_mcp:app --host 127.0.0.1 --port 8002 --reload

# 终端 3：Celery Worker（Agent 层）
celery -A agent.main worker --loglevel=info

# 终端 4：Gateway（主 API 服务）
uvicorn gateway.main:app --host 127.0.0.1 --port 8000 --reload
```

所有服务就绪后，发送测试请求：
```bash
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
```

---

## 11. 测试场景（pytest）

**场景 A（软触发命中）：**
- user_001，生于 1990 年，周六 13:30 发来遥测
- HR=75，glucose=4.8，GPS=(39.9, 116.4)
- `user_weekly_patterns` 存在：day_of_week=5，hour=14，probability=0.85，avg_glucose_drop=2.5
- 期望：`evaluate_soft_triggers` 返回 `InvestigationTask(trigger_type="SOFT_PRE_EXERCISE_LOW_BUFFER")`
- 期望：Reflector 输出 risk_level="MEDIUM"，intervention_action="SOFT_REMIND"
- 期望：Communicator 文案包含"4.8"和"健身"关键词

**场景 B（硬触发命中，Agent 不启动）：**
- glucose=3.1
- 期望：`evaluate_hard_triggers` 返回 True
- 期望：`NotificationService.send_emergency_alert` 被调用一次
- 期望：Celery Task 未入队

**场景 C（无触发）：**
- glucose=6.2，HR=80，无近期运动计划
- 期望：两个 evaluate 函数均返回 False/None
- 期望：无任何通知，无任何 Celery Task

---

## 12. 代码生成规范

1. **全部使用 async/await**，数据库使用 SQLAlchemy 2.0 async session。
2. **LangGraph 节点**均为 `async def`，通过 `await graph.ainvoke(state)` 调用。
3. **Celery Task** 用 `@celery_app.task` 装饰，内部用 `asyncio.run()` 驱动 async graph。
4. **MCP Server** 为独立 FastAPI 进程，Agent 通过 `httpx.AsyncClient` 调用，不直接 import。
5. **配置统一**用 `pydantic-settings` 的 `BaseSettings` 从 `.env` 读取。
6. **日志**使用 `structlog`，输出 JSON 格式。
7. **不使用任何 Docker 相关配置文件**。
