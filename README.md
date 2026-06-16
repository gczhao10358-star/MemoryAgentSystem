# 智忆助理 (MemoryMate)

> 个性化记忆助理系统 ｜ 版本 v2.1

## 项目概述

智忆助理是一款基于大语言模型的个性化记忆 Agent，通过构建用户级持久记忆和会话级上下文，实现多源信息的统一存储与语义检索，持续学习用户偏好和行为模式，提供上下文连贯的个性化交互体验。

## 核心特性

- **统一记忆架构**: `session memory` + `durable memory` + `pinned view` + `memory cache`
- **动态记忆演化 (v2.1 新增)**: LLM 驱动的 ADD/UPDATE/DELETE/NONE 四操作决策，对比新旧记忆智能演化
- **类别感知衰减 (v2.1 新增)**: 6 类记忆类别（身份/偏好/知识/事件/临时/关系），差异化半衰期（14~180 天），常青记忆豁免
- **重要性评分 (v2.1 新增)**: 多维度关键词打分 + 类别加权，过滤低质量记忆
- **会话智能压缩 (v2.1 新增)**: 超过 15 轮自动触发压缩，LLM 总结旧对话 + Memory Flush 补存遗漏
- **混合检索引擎**: 稠密检索 + 稀疏检索 + RRF 融合 + 个性化重排序
- **用户画像学习**: 多维度用户建模，持续学习用户偏好
- **记忆演化机制**: 自动遗忘与强化，保持记忆时效性
- **智能任务调度**: 基于 asyncio 的精准定时提醒系统
- **第三方平台集成**: 支持飞书平台接收提醒消息
- **时间智能解析**: 支持自然语言时间描述（如"明天下午3点"）
- **会议记录解析**: 支持 PDF/DOCX/TXT/MD 格式，智能提取会议信息
- **中文优化**: 基于 jieba 的中文分词和关键词提取

当前推荐的记忆架构说明见：[docs/memory-architecture.md](./docs/memory-architecture.md)

## 文档导航

- 文档总览：[docs/README.md](./docs/README.md)
- 架构说明：[docs/memory-architecture.md](./docs/memory-architecture.md)
- 学习文档：[docs/学习文档.md](./docs/学习文档.md)
- 面试题库索引：[docs/项目面试题库.md](./docs/项目面试题库.md)
- 使用指南：[docs/guides/使用指南.md](./docs/guides/使用指南.md)
- 飞书接入指南：[docs/guides/飞书接入指南.md](./docs/guides/飞书接入指南.md)
- 前端集成示例：[docs/guides/前端集成示例.md](./docs/guides/前端集成示例.md)
- 任务执行实现总结：[docs/reports/任务执行功能实现总结.md](./docs/reports/任务执行功能实现总结.md)
- 测试报告：[docs/reports/TEST_REPORT.md](./docs/reports/TEST_REPORT.md)
- 评审记录：[docs/reports/review.md](./docs/reports/review.md)
- 会议文档解析规划：[docs/plans/meeting_document_parser_plan.md](./docs/plans/meeting_document_parser_plan.md)

## 项目结构

```
记忆助理智能体/
├── memory_assistant/          # 主程序包
│   ├── core/                  # 核心模块
│   │   ├── memory_mate_agent.py    # 主Agent
│   │   ├── memory_manager.py       # 记忆管理器
│   │   ├── workflow_engine.py      # 工作流引擎
│   │   ├── precise_scheduler.py    # 精准任务调度器
│   │   ├── structured_memory.py    # 结构化记忆CRUD
│   │   ├── evolution_engine.py     # 记忆演化引擎
│   │   └── content_filter.py       # 内容过滤
│   ├── models/                # 数据模型
│   │   ├── memory.py               # 记忆模型
│   │   ├── user_profile.py         # 用户画像模型
│   │   └── retrieval.py            # 检索结果模型
│   ├── storage/               # 存储模块
│   │   ├── vector_store.py         # FAISS向量存储
│   │   ├── metadata_store.py       # SQLite元数据存储
│   │   └── memory_storage.py       # 统一存储接口
│   ├── retrieval/             # 检索模块
│   │   ├── hybrid_retrieval.py     # 混合检索引擎
│   │   └── sparse_retrieval.py     # BM25稀疏检索
│   ├── profile/               # 用户画像模块
│   │   ├── profile_manager.py      # 画像管理器
│   │   └── profile_learner.py      # 画像学习器
│   ├── platform/              # 第三方平台集成
│   │   └── lark_adapter.py         # 飞书平台适配器
│   ├── ingestion/             # 文档处理模块
│   │   ├── document_processor.py   # 文档处理主类
│   │   ├── file_loaders.py         # 文件加载器
│   │   ├── meeting_analyzer.py     # 会议分析器
│   │   ├── text_splitter.py        # 文本切片器
│   │   └── models.py               # 数据模型
│   ├── storage/               # 存储模块
│   │   ├── vector_store.py         # FAISS向量存储
│   │   ├── metadata_store.py       # SQLite元数据存储
│   │   ├── memory_storage.py       # 统一存储接口
│   │   └── document_store.py       # 文档存储
│   └── utils/                 # 工具模块
│       ├── llm_client.py           # LLM客户端
│       ├── embedding.py            # 嵌入模型
│       ├── text_processor.py       # 文本处理
│       ├── time_parser.py          # 时间解析器
│       └── datetime_tools.py       # 时间工具
├── api.py                     # FastAPI 后端服务
├── main.py                    # 命令行版本入口
├── config.yaml                # 配置文件
├── requirements.txt           # 依赖列表
├── scripts/                   # 维护脚本和排障脚本
├── start_server.bat           # 服务启动脚本
├── tests/                     # 测试文件目录
└── README.md                  # 说明文档

### 前端项目结构 (Vue 3 + Vite)

```
frontend/
├── package.json               # 前端依赖
├── vite.config.js             # Vite 配置
├── index.html                 # 入口 HTML
├── public/                    # 静态资源
└── src/
    ├── main.js                # Vue 入口
    ├── App.vue                # 根组件
    ├── router/                # Vue Router
    ├── stores/                # Pinia 状态管理
    ├── views/                 # 页面组件
    │   ├── LoginView.vue      # 登录页
    │   ├── ChatView.vue       # 对话页（支持会议记录上传）
    │   ├── MemoriesView.vue   # 记忆库
    │   ├── ProfileView.vue    # 用户画像
    │   ├── StatsView.vue      # 统计页
    │   └── SettingsView.vue   # 设置页（飞书配置）
    ├── layouts/               # 布局组件
    └── styles/                # 样式文件
```

## 快速开始

### 1. 安装依赖

```bash
cd 记忆助理智能体
pip install -r requirements.txt
```

### 2. 配置 API 密钥

推荐使用环境变量，不要把真实密钥提交到仓库。

方式一：使用 `.env` 文件（推荐）

```bash
cp .env.example .env
```

然后编辑 `.env`：

```bash
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-flash
```

方式二：使用本地 `config.yaml`

```bash
cp config.example.yaml config.yaml
```

`config.yaml` 已加入 `.gitignore`，适合放本地私有配置；示例文件 `config.example.yaml` 可安全提交。

### 3. 运行 Web 服务

#### 方式一: 使用启动脚本 (推荐)

```bash
./start.sh
```

#### 方式二: 分别启动后端和前端

**启动后端:**
```bash
.venv\Scripts\python.exe api.py
```

**启动前端开发服务器:**
```bash
cd frontend
npm install
npm run dev
```

前端开发服务器运行在 http://localhost:5173

#### 构建前端生产版本:

```bash
cd frontend
npm install
npm run build
```

### 4. 访问界面

- **前端界面**: http://localhost:8000/app (生产) 或 http://localhost:5173 (开发)
- **API 文档**: http://localhost:8000/docs
- **API 健康检查**: http://localhost:8000/health

## 使用方法

### 基本对话

```python
from memory_assistant.core.memory_mate_agent import MemoryMateAgent

agent = MemoryMateAgent()
await agent.initialize()

# 对话
response = await agent.chat("user_001", "你好，我叫李明")
print(response)

# 系统会自动记住用户信息
response = await agent.chat("user_001", "你知道我的名字吗？")
print(response)  # 会回答"你叫李明"
```

### 显式存储记忆

```python
await agent.remember(
    user_id="user_001",
    content="用户的生日是1995年5月20日",
    memory_type="fact",
    importance=0.9
)
```

### 搜索记忆

```python
memories = await agent.search_memories(
    user_id="user_001",
    query="生日",
    top_k=5
)
```

### 设置提醒任务

```python
from datetime import datetime, timedelta

# 通过对话设置提醒（系统会自动解析时间）
response = await agent.chat("user_001", "明天下午3点提醒我看论文")

# 或直接使用调度器
task = await agent.precise_scheduler.create_reminder(
    user_id="user_001",
    content="看论文",
    reminder_time=datetime.now() + timedelta(days=1),
    title="学习提醒"
)
```

### 配置飞书通知

```python
# 在设置页面配置飞书参数
# 或调用 API
POST /api/platform/lark/config
{
  "user_id": "user_001",
  "app_id": "cli_xxxxxx",
  "app_secret": "xxxxxx",
  "receive_id": "ou_xxxxxx"
}
```

### 上传会议记录

```bash
# 通过前端界面上传
# 支持 PDF、DOCX、TXT、Markdown 格式
# 系统会自动提取会议主题、摘要、决策、待办事项

# 或通过 API 调用
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@meeting.pdf" \
  -F "user_id=user_001" \
  -F "source=web"
```

## 配置说明

### 记忆配置

```yaml
memory:
  session_memory:
    max_turns: 20          # 会话记忆最大轮次

  memory_cache:
    max_entries: 100       # 近期缓存最大条目
    ttl_days: 7            # 近期缓存保留天数

  evolution:
    decay_rate: 0.05       # 记忆基础衰减率（会被类别半衰期覆盖）
    reinforcement_rate: 0.1 # 访问强化速率
    forget_threshold: 0.15 # 遗忘阈值
    archive_threshold: 0.3  # 归档阈值
    core_threshold: 0.8     # 核心记忆阈值
```

说明：
- `session_memory` 负责当前会话线程的上下文拼接。
- `memory_cache` 是近期热点记忆缓存，不是业务真相源。
- 持久记忆以 SQLite + 向量索引为主，`pinned view` 是从持久记忆动态筛出的高价值记忆视图。
- 旧配置名 `working_memory` 和 `short_term_memory` 仍兼容。

### 检索配置

```yaml
retrieval:
  dense:
    top_k: 50              # 稠密检索返回数量

  sparse:
    top_k: 50              # 稀疏检索返回数量

  rrf:
    k: 60                  # RRF平滑参数
```

## API文档

### MemoryMateAgent 类

#### `__init__(config)`
初始化Agent

#### `async initialize()`
异步初始化系统

#### `async chat(user_id, message, stream=False)`
主对话接口

#### `async remember(user_id, content, memory_type="fact", importance=0.5)`
显式存储记忆

#### `async search_memories(user_id, query, top_k=10)`
搜索记忆

#### `async get_user_stats(user_id)`
获取用户统计

#### `async run_evolution()`
运行记忆演化

## 技术细节

### 记忆存储

- **向量数据库**: FAISS (支持高效相似度检索)
- **元数据存储**: SQLite (支持事务和索引)
- **向量维度**: 1024 (默认)

### 检索策略

1. **稠密检索**: 基于向量相似度 (余弦相似度)
2. **稀疏检索**: 基于BM25的关键词匹配
3. **RRF融合**: Reciprocal Rank Fusion算法
4. **个性化重排序**: 基于用户画像调整排序

### 记忆演化 (v2.1)

演化引擎实现两层决策：

**1. 入库时 LLM 演化决策（借鉴 Mem0）**
```
新事实提取 → 向量检索 top-5 旧记忆 → LLM 对比判断:
  - ADD:    新信息，无冲突 → 直接入库
  - UPDATE: 旧信息变化（如地址变更）→ 更新同一 ID，保留变更历史
  - DELETE: 旧信息失效（如"我不再喜欢咖啡"）→ 移除
  - NONE:   与现有记忆完全一致 → 跳过
```

**2. 后台类别感知衰减（借鉴 OpenClaw）**
| 类别 | 半衰期 | 常青 |
|------|--------|------|
| identity（姓名、职业） | 180 天 | 永不过期 |
| preference（喜好、习惯） | 180 天 | 永不过期 |
| relation（人际关系） | 90 天 | 弱衰减 |
| knowledge（技能、知识） | 60 天 | 正常衰减 |
| event（事件记录） | 30 天 | 正常衰减 |
| temporal（临时信息） | 14 天 | 快速衰减 |

- **衰减公式**: `weight *= 0.5^(days / half_life)`
- **访问强化**: `boost = log(1 + access_count) * reinforcement_rate`
- **状态转换**: `NEW → ACTIVE → REINFORCED/CORE` 或 `→ DECAYING → ARCHIVED → FORGOTTEN`

### 会话智能压缩 (v2.1)

借鉴 Claude Code wU2 + OpenClaw Compaction 的设计：
- 触发阈值：会话超过 15 轮
- 保留最近 5 轮不变
- 旧对话由 LLM 生成结构化摘要（关键事实 / 决策 / 待办）
- 压缩前执行 Memory Flush：检测旧对话中遗漏的高价值信息并补存

### 任务调度

- **调度器**: 基于 asyncio 的精准定时调度器
- **精度**: 毫秒级定时精度
- **持久化**: 任务存储在 SQLite，支持服务重启后恢复
- **通知方式**: WebSocket 实时推送 + 飞书平台通知

## 注意事项

1. **API密钥安全**: 不要在代码中硬编码API密钥，建议使用环境变量
2. **隐私保护**: 用户数据存储在本地，不会上传到云端
3. **内存使用**: 向量索引会占用内存，大量数据时可能需要调整batch_size
4. **定期演化**: 建议定期运行记忆演化以保持记忆质量

## Web 服务

### 启动 Web 服务

```bash
# 使用启动脚本
start_server.bat

# 或直接启动
python api.py
```

### 访问界面

- **前端界面**: http://localhost:8000/app
- **API 文档**: http://localhost:8000/docs
- **API 健康检查**: http://localhost:8000/health

### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/users` | 创建用户 |
| POST | `/api/chat` | 对话 |
| POST | `/api/remember` | 存储记忆 |
| POST | `/api/search` | 搜索记忆 |
| GET | `/api/stats/{user_id}` | 获取统计 |
| POST | `/api/clear` | 清空对话 |
| **任务管理** ||
| POST | `/api/tasks` | 创建定时任务/提醒 |
| GET | `/api/tasks/{user_id}` | 获取用户任务列表 |
| DELETE | `/api/tasks/{task_id}` | 取消任务 |
| **时间解析** ||
| POST | `/api/parse-time` | 解析自然语言时间 |
| POST | `/api/search-by-time` | 按时间范围搜索记忆 |
| **飞书平台** ||
| POST | `/api/platform/lark/config` | 保存飞书配置 |
| POST | `/api/platform/lark/test` | 测试飞书连接 |
| GET | `/api/platform/status` | 获取平台状态 |
| DELETE | `/api/platform/lark/config` | 删除飞书配置 |
| **WebSocket** ||
| WS | `/ws/{user_id}` | 实时提醒推送 |
| **文档处理** ||
| POST | `/api/documents/upload` | 上传会议记录文档 |
| WS | `/ws/documents/{document_id}` | 文档处理进度推送 |
| POST | `/api/documents/confirm-actions` | 确认创建待办提醒 |
| GET | `/api/documents/{user_id}` | 获取用户文档列表 |
| GET | `/api/documents/{document_id}` | 获取文档详情 |

## 前端功能

- 💬 **实时对话**: 流畅的聊天体验，支持自然语言设置提醒
- 📝 **记忆管理**: 查看、搜索、添加、删除记忆
- 📄 **会议记录**: 上传会议文档，智能提取摘要、决策、待办
- 👤 **用户画像**: 展示学习到的用户偏好
- 📊 **数据统计**: 记忆和对话统计可视化
- ⏰ **任务提醒**: 查看和管理定时提醒任务
- 🔗 **平台集成**: 飞书平台配置和测试
- ⚙️ **系统设置**: 第三方平台接入配置

## 数据持久化

- **向量存储**: `./data/vector_index/`
- **元数据存储**: `./data/memory.db` (SQLite)
- **用户画像**: `./data/profiles/`

## 更新日志

### v2.1 (2026-06-16)
- **动态记忆演化**: LLM 驱动的 ADD/UPDATE/DELETE/NONE 四操作决策引擎
- **类别感知衰减**: 6 类记忆差异化半衰期 + 常青记忆豁免（ID/PREF 永不过期）
- **重要性评分**: 多维度关键词评分 + 类别加权
- **会话智能压缩**: 15 轮触发 LLM 摘要压缩 + Memory Flush 补存
- **存储层**: `memories` 表新增 `category` 列（兼容旧数据迁移）

### v2.0 (2026-06-16)
- 鲁棒性大修：时间漂移修复、LLM 错误过滤、路由全类型召回、CHAT 注入画像、STORE 查重、LLM Rerank

### v1.3 (2026-03-14)
- 新增会议记录文档解析功能
- 支持 PDF、DOCX、TXT、Markdown 格式上传
- 智能提取会议主题、摘要、决策、待办事项
- 修复飞书通知时区问题
- 修复 Windows 控制台编码问题
- 优化任务调度回调机制
- 前端分析结果支持持久化和重新查看

### v1.2 (2026-03-12)
- 重构任务调度系统，统一使用 asyncio 精准调度器
- 新增飞书平台集成，支持双通道提醒
- 添加时间智能解析功能
- 新增设置页面，支持飞书配置管理

### v1.1 (2026-03-11)
- 添加任务执行/提醒功能
- 新增 WebSocket 实时推送
- 优化工作流引擎

### v1.0 (2026-03-10)
- 初始版本发布
- 实现早期分层记忆架构
- 完成混合检索引擎
- 添加用户画像学习

## 未来计划

- [x] Web界面
- [x] 任务调度/提醒系统
- [x] 第三方平台集成 (飞书)
- [x] 会议记录文档解析
- [x] 类别感知记忆衰减
- [x] LLM 驱动的记忆演化决策
- [x] 会话智能压缩

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！
