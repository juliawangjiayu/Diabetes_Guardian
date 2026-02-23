# agent.md — 糖尿病智能监护系统工程规范

本文件是 AI 编程助手的行为准则。在生成、修改任何代码前，必须完整阅读本文件。

---

## 1. 项目概览

```
项目名称：diabetes-guardian
后端语言：Python 3.11+
核心框架：FastAPI + LangGraph + Celery
数据层：  MySQL 8.0 (SQLAlchemy 2.0 async) + Redis 7
运行方式：本地虚拟环境（uv），无 Docker
```

### 服务端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| Gateway API | 8000 | 主入口，接收 App 遥测数据 |
| Patient History MCP | 8001 | 历史数据查询工具服务 |
| Location Context MCP | 8002 | 地理语义解析工具服务 |
| MySQL | 3306 | 本地安装，不改端口 |
| Redis | 6379 | 本地安装，不改端口 |

---

## 2. 目录与文件规范

### 2.1 目录职责边界（严格遵守，不得跨层调用）

```
gateway/        → 只负责接收请求、触发判断、写库、入队
agent/          → 只负责 LangGraph 工作流编排和 LLM 调用
mcp_servers/    → 只负责封装数据查询，对外暴露 HTTP 工具接口
db/             → 只放 ORM 模型和 SQL 文件，不含业务逻辑
tests/          → 镜像主目录结构，文件名前缀 test_
```

**禁止行为：**
- `agent/` 内不得直接 import SQLAlchemy session 查数据库，必须通过 MCP Server HTTP 接口
- `gateway/` 内不得 import `agent/` 的任何模块
- `mcp_servers/` 内不得 import `gateway/` 或 `agent/` 的任何模块

### 2.2 文件命名

- Python 文件：`snake_case.py`
- 类名：`PascalCase`
- 函数 / 变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- Pydantic 模型：以数据含义命名，不加 `Model` 后缀（用 `TelemetryPayload` 而非 `TelemetryModel`）

### 2.3 每个文件顶部必须包含模块说明注释

```python
"""
gateway/services/triage.py

职责：硬触发与软触发判断逻辑。
- evaluate_hard_triggers: 极危情况直接告警，不唤醒 Agent
- evaluate_soft_triggers: 维护滑动窗口，命中后入队唤醒 Agent
"""
```

---

## 3. Python 编码规范

### 3.1 基础要求

- Python 版本：**3.11+**，使用 `match` 语句替代多层 `if-elif`（适用于 trigger_type 分发）
- 类型注解：**所有函数参数和返回值必须标注类型**，不允许裸 `Any`
- 格式化工具：`ruff format`（替代 black），提交前必须通过
- Lint 工具：`ruff check`，0 warning 才允许提交

```python
# ✅ 正确
async def evaluate_hard_triggers(
    payload: TelemetryPayload,
    user_age: int,
) -> bool:
    ...

# ❌ 禁止——缺少类型注解
async def evaluate_hard_triggers(payload, user_age):
    ...
```

### 3.2 async/await 规范

- **所有 I/O 操作必须是 async**：数据库、Redis、HTTP 调用、LLM API 均不允许使用同步阻塞版本
- 并发调用使用 `asyncio.gather()`，不允许串行 `await` 可以并行的操作

```python
# ✅ 正确 —— 并发执行
location, history = await asyncio.gather(
    call_location_context_mcp(lat, lng, user_id),
    call_patient_history_mcp(user_id, reference_time),
)

# ❌ 禁止 —— 串行浪费时间
location = await call_location_context_mcp(lat, lng, user_id)
history = await call_patient_history_mcp(user_id, reference_time)
```

- Celery Task 内部驱动 async 代码，统一使用 `asyncio.run()`

```python
@celery_app.task(name="agent.tasks.run_investigation")
def run_investigation(task_json: str) -> None:
    asyncio.run(_run_graph(task_json))
```

### 3.3 错误处理规范

所有外部调用（数据库、MCP HTTP、LLM API）必须用 try/except 包裹，**不允许裸 `except Exception`**：

```python
# ✅ 正确 —— 明确异常类型 + 降级行为
try:
    result = await httpx_client.post(url, json=payload, timeout=5.0)
    result.raise_for_status()
except httpx.TimeoutException:
    logger.warning("mcp_timeout", service=service_name, url=url)
    return default_fallback_value
except httpx.HTTPStatusError as e:
    logger.error("mcp_http_error", status=e.response.status_code)
    return default_fallback_value

# ❌ 禁止
try:
    result = await httpx_client.post(url, ...)
except Exception:
    pass
```

**降级返回值约定：**

| 调用方 | 失败时返回 |
|--------|-----------|
| `call_location_context_mcp` | `{"semantic_location": "未知位置", "is_at_home": False, "nearby_known_places": []}` |
| `call_patient_history_mcp` | `{"glucose_history_24h": [], "upcoming_activity": None, "recent_exercise_drops": []}` |
| LLM Reflector | `{"risk_level": "MEDIUM", "reasoning_summary": "LLM 不可用，执行规则兜底", "intervention_action": "SOFT_REMIND"}` |

### 3.5 注释语言规范

**所有代码文件中的注释必须使用英语**，包括行内注释、块注释、docstring、模块说明注释。

```python
# ✅ Correct
# Calculate the slope of glucose readings over the past 20 minutes
slope = np.polyfit(timestamps, glucose_values, 1)[0]

# ✅ Correct — docstring in English
async def evaluate_soft_triggers(
    payload: TelemetryPayload,
    user_age: int,
) -> Optional[InvestigationTask]:
    """
    Evaluate soft trigger conditions using a sliding window of recent telemetry.

    Returns an InvestigationTask if a soft trigger condition is met,
    otherwise returns None.
    """

# ❌ Forbidden — Chinese comments in code
# 计算过去 20 分钟的血糖斜率
slope = np.polyfit(timestamps, glucose_values, 1)[0]
```

**唯一例外**：LLM 的 `SYSTEM_PROMPT` 和 `COMMUNICATOR_PROMPT` 常量字符串内容面向中文用户，允许使用中文。但定义这些常量的行内注释仍须用英语：

```python
# System prompt injected into the reflector node for clinical reasoning
SYSTEM_PROMPT = """
你是一名专业的糖尿病管理 AI 助手……
"""
```

### 3.4 HTTP 客户端规范

所有 MCP Server 调用必须复用单例 `httpx.AsyncClient`，不允许在函数内部 `httpx.AsyncClient()` 每次新建：

```python
# mcp_servers/client.py —— 统一在此管理客户端生命周期
from contextlib import asynccontextmanager
import httpx

_client: httpx.AsyncClient | None = None

def get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized")
    return _client

@asynccontextmanager
async def lifespan(app):
    global _client
    _client = httpx.AsyncClient(timeout=5.0)
    yield
    await _client.aclose()
```

所有 HTTP 请求必须设置 `timeout=5.0`，最多重试 2 次（指数退避 1s → 2s）。

---

## 4. 配置管理规范

### 4.1 统一使用 pydantic-settings

```python
# config.py（项目根目录，各模块 import 此处）
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: str
    mysql_db: str

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # LLM
    openai_api_key: str
    llm_model: str = "gpt-4o"

    # MCP Servers
    patient_history_mcp_url: str = "http://127.0.0.1:8001"
    location_context_mcp_url: str = "http://127.0.0.1:8002"

    # 推送
    fcm_server_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**禁止行为：**
- 不允许在任何非 `config.py` 的文件中直接 `os.getenv()`
- 不允许硬编码任何 IP、端口、密钥、模型名称

---

## 5. 数据库规范

### 5.1 SQLAlchemy 2.0 async 写法

```python
# ✅ 正确 —— 使用 async session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    f"mysql+aiomysql://{settings.mysql_user}:{settings.mysql_password}"
    f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_db}",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # 自动检测断连
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 使用方式
async with AsyncSessionLocal() as session:
    result = await session.execute(select(UserTelemetryLog).where(...))
```

### 5.2 查询规范

- 只允许在 `db/` 和 `mcp_servers/` 内写 SQL / ORM 查询
- 所有查询必须带 `user_id` 过滤，禁止全表扫描
- 分页查询必须带 `LIMIT`，上限 1000 条
- `mcp_servers/patient_history_mcp.py` 的 NL2SQL 接口必须在执行前校验 SQL：
  - 只允许 `SELECT`，检测到 `DROP / UPDATE / DELETE / INSERT` 立即返回 400 错误
  - SQL 长度上限 2000 字符

---

## 6. LangGraph 规范

### 6.1 State 字段只增不改

`AgentState` 中已定义的字段名称和类型不允许修改，只允许新增字段。新增字段必须是 `Optional` 并有默认值 `None`。

### 6.2 节点函数签名

所有 LangGraph 节点必须是纯函数风格（输入 state，输出 state 的部分更新）：

```python
# ✅ 正确 —— 只返回本节点负责更新的字段
async def investigator_node(state: AgentState) -> dict:
    ...
    return {
        "location_context": location_result["semantic_location"],
        "glucose_history_24h": history_result["glucose_history_24h"],
        "upcoming_activity": history_result["upcoming_activity"],
        "recent_exercise_glucose_drops": history_result["recent_exercise_drops"],
    }

# ❌ 禁止 —— 不要返回完整 state（容易覆盖其他节点的写入）
async def investigator_node(state: AgentState) -> AgentState:
    return {**state, "location_context": ...}
```

### 6.3 LLM 调用规范

- Reflector 和 Communicator 的 System Prompt 定义为模块级常量（`SYSTEM_PROMPT`），不允许在函数内部拼接
- LLM 输出必须要求返回 JSON，并用 try/except 包裹 `json.loads()`，解析失败时触发降级规则
- LLM 调用必须设置 `max_tokens`（Reflector: 512，Communicator: 256）
- 不允许在 Agent 层直接使用 `print()` 调试，必须用 `structlog`

---

## 7. MCP Server 规范

### 7.1 接口设计原则

- 每个 MCP Server 只暴露 `POST /tools/<tool_name>` 风格的端点
- 请求和响应均为 Pydantic 模型，不允许裸 `dict`
- 每个工具函数执行时间必须在 3 秒内完成（配合调用方的 timeout=5.0）

### 7.2 NL2SQL 安全规范（patient_history_mcp.py 专属）

```python
FORBIDDEN_KEYWORDS = {"drop", "delete", "update", "insert", "alter", "truncate", "create"}

def validate_sql(sql: str) -> None:
    lower = sql.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            raise ValueError(f"禁止的 SQL 操作: {kw}")
    if len(sql) > 2000:
        raise ValueError("SQL 长度超出限制")
```

### 7.3 Haversine 距离计算（location_context_mcp.py 专属）

使用标准公式，地球半径取 6371 km，距离单位统一为**米（int）**：

```python
import math

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    R = 6_371_000  # 地球半径，单位：米
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return int(2 * R * math.asin(math.sqrt(a)))
```

---

## 8. 日志规范

统一使用 `structlog`，禁止 `print()`，禁止 `logging.basicConfig()`。

```python
# 在每个模块顶部初始化
import structlog
logger = structlog.get_logger(__name__)

# 使用示例
logger.info("soft_trigger_fired", user_id=user_id, glucose=glucose, trigger_type="SOFT_PRE_EXERCISE_LOW_BUFFER")
logger.warning("mcp_timeout", service="patient_history", elapsed_ms=3200)
logger.error("llm_parse_failed", raw_response=raw, fallback="rule_based")
```

**日志字段约定：**

| 关键字段 | 类型 | 说明 |
|----------|------|------|
| `user_id` | str | 所有日志必须携带 |
| `trigger_type` | str | 触发类型，触发相关日志必须携带 |
| `elapsed_ms` | int | 外部调用耗时，超时日志必须携带 |
| `service` | str | 被调用的下游服务名 |
| `fallback` | str | 使用了何种降级策略 |

---

## 9. 测试规范

### 9.1 测试文件结构镜像主目录

```
tests/
├── fixtures.py              # 共享测试数据（用户画像、遥测样本）
├── test_triage.py           # 对应 gateway/services/triage.py
├── test_graph.py            # 对应 agent/graph.py（完整流程集成测试）
├── test_patient_history_mcp.py
└── test_location_context_mcp.py
```

### 9.2 必须覆盖的测试场景

每个触发函数必须有以下三类测试：
1. **命中测试**：输入边界值，断言触发
2. **未命中测试**：输入安全值，断言不触发
3. **降级测试**：Mock 外部依赖抛出异常，断言降级行为正确

```python
# 示例风格
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_hard_trigger_fires_on_low_glucose():
    payload = build_telemetry(glucose=3.1)
    result = await evaluate_hard_triggers(payload, user_age=34)
    assert result is True

@pytest.mark.asyncio
async def test_hard_trigger_skips_on_normal_glucose():
    payload = build_telemetry(glucose=5.5)
    result = await evaluate_hard_triggers(payload, user_age=34)
    assert result is False

@pytest.mark.asyncio
async def test_investigator_node_degrades_on_mcp_timeout():
    with patch("agent.nodes.investigator.call_location_context_mcp", side_effect=httpx.TimeoutException("timeout")):
        state = build_initial_state()
        result = await investigator_node(state)
        assert result["location_context"] == "未知位置"
```

### 9.3 禁止在测试中连接真实服务

- 所有数据库调用必须 Mock
- 所有 HTTP（MCP、LLM）调用必须 Mock
- 所有 Celery Task 在测试中使用 `CELERY_TASK_ALWAYS_EAGER=True`

---

## 10. 医学常量规范

所有医学相关阈值定义在 `gateway/constants.py`，不允许在业务代码中出现魔法数字：

```python
# gateway/constants.py

# 血糖阈值（mmol/L）
GLUCOSE_HARD_LOW = 3.9          # 硬触发：极低血糖
GLUCOSE_SOFT_LOW_MIN = 4.0      # 软触发：运动预备区间下限
GLUCOSE_SOFT_LOW_MAX = 5.6      # 软触发：运动预备区间上限
GLUCOSE_EXERCISE_SAFE_MIN = 5.6 # 高强度运动前安全下限
GLUCOSE_EXERCISE_SAFE_MAX = 10.0

# 心率阈值
MAX_HR_RATIO = 0.90             # (220 - age) × 0.90

# 时间窗口（分钟）
TELEMETRY_GAP_ALERT_MIN = 30    # 数据中断告警阈值
SLOPE_WINDOW_MIN = 20           # 血糖斜率滑动窗口
PRE_EXERCISE_WARN_MIN = 60      # 运动前预警提前量

# 软触发概率阈值
ACTIVITY_PROBABILITY_THRESHOLD = 0.70

# 血糖斜率触发阈值（mmol/L/min）
GLUCOSE_SLOPE_TRIGGER = -0.1

# 位置判定（米）
KNOWN_PLACE_RADIUS_M = 200
```

---

## 11. 禁止事项汇总（快速参考）

| # | 禁止行为 |
|---|----------|
| 1 | 生成任何 `Dockerfile` 或 `docker-compose.yml` |
| 2 | 在 `agent/` 层直接查询数据库 |
| 3 | 在函数内部硬编码 IP、端口、API Key、模型名 |
| 4 | 使用 `except Exception: pass` 静默吞掉错误 |
| 5 | 串行 `await` 本可并发的 I/O 操作 |
| 6 | 在测试中连接真实 MySQL / Redis / LLM |
| 7 | 在业务代码中出现医学数值魔法数字（必须引用 `constants.py`） |
| 8 | LangGraph 节点返回完整 `{**state, ...}`（只返回本节点写入的字段）|
| 9 | MCP NL2SQL 接口执行非 SELECT 语句 |
| 10 | 使用 `print()` 调试，必须用 `structlog` |
| 11 | 在代码文件中使用中文注释（SYSTEM_PROMPT 字符串内容除外）|
