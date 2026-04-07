# 智忆助理 (MemoryMate) - 个性化长期记忆智能体系统

## 详细设计文档

> **版本**: v1.0
> **日期**: 2026-03-10
> **项目性质**: 中期汇报文档

---

## 目录

1. [项目概述](#一项目概述)
2. [系统架构设计](#二系统架构设计)
3. [系统模块设计](#三系统模块设计)
4. [核心流程活动图](#四核心流程活动图)
5. [详细设计](#五详细设计)
6. [用户画像与个性化](#六用户画像与个性化设计)

---

## 一、项目概述

### 1.1 项目背景

在信息爆炸的时代，个人每天产生海量数据（聊天记录、会议记录、待办事项、文档、日程安排），这些信息分散在不同平台，难以统一管理和高效检索。传统搜索依赖关键词匹配，无法理解语义上下文，导致信息查找效率低下。

**智忆助理**是一款基于大语言模型和长期记忆机制的智能Agent，通过构建个性化知识库，实现：
- 多源信息的统一存储与语义检索
- 用户偏好和行为的持续学习
- 上下文连贯的个性化交互

### 1.2 核心创新点

| 创新点 | 说明 |
|--------|------|
| **分层记忆架构** | 三级记忆模型：工作记忆→短期记忆→长期记忆 |
| **动态记忆演化** | 记忆权重自动更新，支持主动遗忘机制 |
| **个性化用户画像** | 多维度用户建模，持续学习用户偏好 |
| **主动记忆召回** | 不仅响应查询，主动推送相关历史信息 |
| **可信度评估** | 区分确认事实与推测信息 |

---

## 二、系统架构设计

### 2.1 总体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           智忆助理 (MemoryMate)                              │
│                         个性化长期记忆智能体系统                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         交互层 (Interface Layer)                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │   │
│  │  │  聊天接口 │  │  语音接口 │  │  网页界面 │  │  第三方API (日程/邮件) │ │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘ │   │
│  └───────┼─────────────┼─────────────┼───────────────────┼─────────────┘   │
│          │             │             │                   │                  │
│          └─────────────┴─────────────┴───────────────────┘                  │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         认知层 (Cognition Layer)                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    核心智能体引擎                            │   │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │   │
│  │  │  │  意图理解模块 │  │  任务规划模块 │  │  响应生成模块     │  │   │   │
│  │  │  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │   │   │
│  │  └─────────┼─────────────────┼──────────────────┼────────────┘   │   │
│  │            │                 │                  │                 │   │
│  │            ▼                 ▼                  ▼                 │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │              记忆管理引擎 (Memory Engine)                    │ │   │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐ │ │   │
│  │  │  │ 工作记忆   │ │ 短期记忆   │ │ 长期记忆   │ │ 用户画像  │ │ │   │
│  │  │  │ (上下文)   │ │ (会话历史) │ │ (知识库)   │ │ 建模      │ │ │   │
│  │  │  └────────────┘ └────────────┘ └─────┬──────┘ └───────────┘ │ │   │
│  │  └─────────────────────────────────────┼──────────────────────┘ │   │
│  └────────────────────────────────────────┼────────────────────────┘   │
│                                           │                              │
│                                           ▼                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         存储层 (Storage Layer)                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  向量数据库   │  │  关系数据库   │  │  对象存储     │              │   │
│  │  │  (FAISS)     │  │  (SQLite)    │  │  (文件系统)   │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流架构

```
用户输入
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│  阶段1: 输入处理                                                 │
│  - 多模态解析 (文本/语音/图片)                                    │
│  - 实体识别 (人名/地点/时间/事件)                                 │
│  - 意图分类 (查询/记录/提醒/闲聊)                                 │
└────────────────────────────┬───────────────────────────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  查询类意图   │   │  记录类意图   │   │  交互类意图   │
│  (Retrieve)   │   │  (Store)      │   │  (Chat)       │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ 记忆检索引擎  │   │ 记忆存储引擎  │   │ 上下文构建    │
│ - 语义搜索    │   │ - 向量化      │   │ - 工作记忆    │
│ - 关联召回    │   │ - 元数据提取  │   │ - 个性化prompt│
│ - 时效性过滤  │   │ - 可信度评估  │   │               │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  阶段2: 记忆融合                                                 │
│  - 检索结果去重与排序                                             │
│  - 记忆可信度加权                                                 │
│  - 用户画像增强                                                   │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│  阶段3: 响应生成                                                 │
│  - 上下文构建 (System Prompt + Memory + Query)                   │
│  - LLM推理                                                       │
│  - 响应后处理 (引用来源/置信度标注)                               │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
                          用户输出
```

---

## 三、系统模块设计

### 3.1 模块划分

```
智忆助理系统
│
├── 1. 输入处理模块 (InputProcessor)
│   ├── 1.1 多模态解析器
│   ├── 1.2 实体识别器
│   └── 1.3 意图分类器
│
├── 2. 记忆管理模块 (MemoryManager) [核心]
│   ├── 2.1 工作记忆管理器 (WorkingMemory)
│   ├── 2.2 短期记忆管理器 (ShortTermMemory)
│   ├── 2.3 长期记忆管理器 (LongTermMemory)
│   ├── 2.4 记忆检索引擎 (MemoryRetrieval)
│   └── 2.5 记忆演化引擎 (MemoryEvolution)
│
├── 3. 用户画像模块 (UserProfileManager)
│   ├── 3.1 画像建模器
│   ├── 3.2 偏好学习器
│   └── 3.3 行为分析器
│
├── 4. 知识处理模块 (KnowledgeProcessor)
│   ├── 4.1 文档解析器
│   ├── 4.2 文本分块器
│   ├── 4.3 向量化器
│   └── 4.4 索引构建器
│
├── 5. 智能体核心模块 (AgentCore)
│   ├── 5.1 任务规划器
│   ├── 5.2 上下文构建器
│   └── 5.3 响应生成器
│
└── 6. 存储模块 (StorageLayer)
    ├── 6.1 向量存储 (VectorStore)
    ├── 6.2 元数据存储 (MetadataStore)
    └── 6.3 文件存储 (FileStore)
```

### 3.2 核心类设计

#### 3.2.1 记忆管理核心类

```python
class MemoryManager:
    """
    记忆管理器 - 系统核心组件
    协调三级记忆的存取与演化
    """
    def __init__(self):
        self.working_memory: WorkingMemory      # 工作记忆 (当前会话)
        self.short_term_memory: ShortTermMemory  # 短期记忆 (近期会话)
        self.long_term_memory: LongTermMemory    # 长期记忆 (永久存储)
        self.evolution_engine: MemoryEvolutionEngine  # 演化引擎

    async def memorize(self, event: UserEvent) -> MemoryEntry:
        """将事件存入记忆系统"""
        # 1. 存入工作记忆
        entry = await self.working_memory.store(event)

        # 2. 异步持久化到长期记忆
        await self.long_term_memory.persist(entry)

        # 3. 更新用户画像
        await self.update_user_profile(event)

        return entry

    async def recall(self, query: str, user_id: str,
                     context: RecallContext) -> List[MemoryEntry]:
        """从记忆系统检索相关信息"""
        # 1. 检索长期记忆
        long_term_results = await self.long_term_memory.search(
            query, user_id, top_k=10
        )

        # 2. 检索短期记忆
        short_term_results = await self.short_term_memory.get_recent(
            user_id, limit=20
        )

        # 3. 融合排序
        fused_results = self.fuse_memories(
            long_term_results, short_term_results, query
        )

        # 4. 个性化重排序
        ranked_results = await self.personalize_ranking(
            fused_results, user_id
        )

        return ranked_results


class MemoryEntry:
    """
    记忆条目 - 统一记忆数据结构
    """
    memory_id: str              # 唯一标识
    user_id: str                # 所属用户
    content: str                # 记忆内容
    memory_type: MemoryType     # 记忆类型

    # 时间属性
    created_at: datetime        # 创建时间
    updated_at: datetime        # 更新时间
    last_accessed: datetime     # 最后访问

    # 质量属性
    confidence: float           # 可信度 (0-1)
    importance: float           # 重要性 (0-1)
    access_count: int           # 访问次数

    # 关联属性
    tags: List[str]             # 标签
    related_entities: List[str] # 关联实体
    source: str                 # 来源

    # 向量表示 (用于语义检索)
    embedding: Optional[List[float]]


class UserProfile:
    """
    用户画像 - 多维度用户建模
    """
    user_id: str

    # 基础属性
    basic_info: Dict[str, Any]      # 基本信息
    preferences: UserPreferences     # 偏好设置

    # 行为模式
    behavior_patterns: List[Pattern] # 行为模式
    communication_style: str         # 沟通风格

    # 知识领域
    expertise_areas: List[str]       # 专业领域
    interest_topics: List[str]       # 兴趣话题

    # 记忆统计
    memory_stats: MemoryStatistics   # 记忆统计

    # 时间特征
    active_hours: List[int]          # 活跃时段
    response_patterns: Dict[str, Any] # 响应模式


class MemoryEvolutionEngine:
    """
    记忆演化引擎 - 实现动态遗忘与强化
    """
    def __init__(self):
        self.decay_factor = 0.95        # 衰减因子
        self.reinforcement_rate = 0.1   # 强化速率
        self.forget_threshold = 0.1     # 遗忘阈值

    async def evolve(self, memory: MemoryEntry):
        """执行记忆演化"""
        # 1. 时间衰减
        days_passed = (now() - memory.last_accessed).days
        time_decay = self.decay_factor ** days_passed

        # 2. 访问强化
        access_boost = 1 + (memory.access_count * self.reinforcement_rate)

        # 3. 重要性基准
        base_importance = memory.importance

        # 4. 计算新权重
        new_weight = base_importance * time_decay * access_boost
        memory.weight = min(new_weight, 1.0)

        # 5. 遗忘判断
        if memory.weight < self.forget_threshold:
            await self.archive_or_delete(memory)
```

### 3.3 存储设计

#### 3.3.1 数据模型

```sql
-- 记忆主表
CREATE TABLE memories (
    memory_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    memory_type VARCHAR(20) NOT NULL,  -- 'chat', 'document', 'event', 'fact'

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,

    -- 质量指标
    confidence FLOAT DEFAULT 0.5,      -- 可信度
    importance FLOAT DEFAULT 0.5,      -- 重要性
    weight FLOAT DEFAULT 0.5,          -- 当前权重
    access_count INT DEFAULT 0,        -- 访问次数

    -- 元数据
    source VARCHAR(100),               -- 来源
    source_id VARCHAR(36),             -- 源ID
    tags JSON,                         -- 标签数组
    related_entities JSON,             -- 关联实体

    -- 向量ID (外键关联向量存储)
    vector_id VARCHAR(36),

    INDEX idx_user_time (user_id, created_at),
    INDEX idx_weight (user_id, weight),
    FULLTEXT INDEX idx_content (content)
);

-- 用户画像表
CREATE TABLE user_profiles (
    user_id VARCHAR(36) PRIMARY KEY,

    -- 偏好设置 (JSON)
    preferences JSON,

    -- 行为模式
    communication_style VARCHAR(50),
    expertise_areas JSON,
    interest_topics JSON,

    -- 时间特征
    active_hours JSON,

    -- 统计信息
    total_memories INT DEFAULT 0,
    total_interactions INT DEFAULT 0,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 记忆关联表 (用于构建记忆图谱)
CREATE TABLE memory_relations (
    relation_id VARCHAR(36) PRIMARY KEY,
    source_memory VARCHAR(36),
    target_memory VARCHAR(36),
    relation_type VARCHAR(20),         -- 'similar', 'sequential', 'causal'
    strength FLOAT,                     -- 关联强度

    FOREIGN KEY (source_memory) REFERENCES memories(memory_id),
    FOREIGN KEY (target_memory) REFERENCES memories(memory_id)
);
```

---

## 四、核心流程活动图

### 4.1 记忆存储流程

```
┌─────────┐     ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  开始   │────▶│ 接收用户输入 │────▶│  多模态解析     │────▶│ 实体识别    │
└─────────┘     └─────────────┘     └─────────────────┘     └──────┬──────┘
                                                                    │
                                                                    ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐   ┌─────────────┐
│  结束       │◀────│ 异步持久化到    │◀────│ 存入工作记忆    │◀──│ 意图分类    │
│  (返回结果) │     │ 长期记忆存储    │     │ (当前会话)      │   └─────────────┘
└─────────────┘     └─────────────────┘     └─────────────────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │ 提取记忆特征    │
                    │ - 关键词        │
                    │ - 情感倾向      │
                    │ - 重要实体      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ 生成向量嵌入    │
                    │ (Embedding)     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ 可信度评估      │
                    │ (Confidence)    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ 更新用户画像    │
                    │ (学习用户特征)  │
                    └─────────────────┘
```

### 4.2 记忆检索流程

```
┌─────────┐     ┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  开始   │────▶│ 接收查询    │────▶│ 查询理解        │────▶│ 实体链接        │
│         │     │             │     │ (意图/实体)     │     │ (链接已知实体)  │
└─────────┘     └─────────────┘     └─────────────────┘     └────────┬────────┘
                                                                       │
                    ┌──────────────────────────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │    并行检索分支       │
         └──────────┬───────────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│ 语义检索   │ │ 关键词检索 │ │ 图谱检索   │
│ (向量相似) │ │ (BM25)     │ │ (关系遍历) │
└──────┬─────┘ └──────┬─────┘ └──────┬─────┘
       │              │              │
       └──────────────┼──────────────┘
                      │
                      ▼
              ┌─────────────────┐
              │ 结果融合 (RRF)  │
              │ Reciprocal Rank │
              │ Fusion          │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ 时效性过滤      │
              │ (时间衰减加权)  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ 个性化重排序    │
              │ (基于用户画像)  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ 可信度筛选      │
              │ (阈值过滤)      │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ 返回 Top-K      │
              │ 记忆结果        │
              └─────────────────┘
```

### 4.3 用户画像更新流程

```
┌─────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  触发   │────▶│ 提取交互特征    │────▶│ 更新实时统计    │────▶│ 检测模式变化    │
│  事件   │     │ - 查询主题      │     │ - 访问频率      │     │                 │
│         │     │ - 情感倾向      │     │ - 活跃时段      │     │                 │
│         │     │ - 交互深度      │     │ - 偏好强度      │     │                 │
└─────────┘     └─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                                          │
                             ┌───────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ 是否需要更新    │
                    │ 画像模型?       │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
              ┌─────────┐       ┌─────────┐
              │   是    │       │   否    │
              └────┬────┘       └────┬────┘
                   │                 │
                   ▼                 ▼
        ┌─────────────────┐   ┌─────────────┐
        │ 增量学习更新    │   │ 跳过更新    │
        │ - 偏好权重调整  │   │             │
        │ - 新兴趣发现    │   │             │
        │ - 行为模式更新  │   │             │
        └────────┬────────┘   └─────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ 更新用户画像DB  │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ 触发记忆重索引  │
        │ (个性化相关)    │
        └─────────────────┘
```

### 4.4 记忆演化流程

```
┌─────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 定时    │────▶│ 扫描待演化记忆  │────▶│ 计算时间衰减    │
│ 触发    │     │ (按批次)        │     │ Decay Factor    │
│ (每日)  │     │                 │     │                 │
└─────────┘     └─────────────────┘     └────────┬────────┘
                                                  │
                                                  ▼
                                         ┌─────────────────┐
                                         │ 计算访问强化    │
                                         │ Access Boost    │
                                         └────────┬────────┘
                                                  │
                                                  ▼
                                         ┌─────────────────┐
                                         │ 计算新权重      │
                                         │ Weight = Base   │
                                         │   * Decay       │
                                         │   * Boost       │
                                         └────────┬────────┘
                                                  │
                                                  ▼
                                         ┌─────────────────┐
                                         │ 权重 >= 阈值?   │
                                         └────────┬────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                             │                             │
                    ▼                             ▼                             ▼
            ┌───────────────┐             ┌───────────────┐             ┌───────────────┐
            │   是 (保留)   │             │   是 (归档)   │             │   否 (遗忘)   │
            │ 权重正常      │             │ 低权重但重要  │             │ 权重过低      │
            └───────┬───────┘             └───────┬───────┘             └───────┬───────┘
                    │                             │                             │
                    ▼                             ▼                             ▼
            ┌───────────────┐             ┌───────────────┐             ┌───────────────┐
            │ 更新权重      │             │ 移入归档存储  │             │ 软删除标记    │
            │ 继续保留      │             │ (冷存储)      │             │ 或永久删除    │
            └───────────────┘             └───────────────┘             └───────────────┘
```

---

## 五、详细设计

### 5.1 记忆保存机制

#### 5.1.1 三级记忆架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        记忆保存架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: 工作记忆 (Working Memory)                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - 存储位置: 内存 (Redis/Memory)                         │   │
│  │  - 容量限制: 当前会话上下文 (约4k-8k tokens)             │   │
│  │  - 保留时间: 会话期间                                    │   │
│  │  - 存储内容: 当前对话历史、临时上下文                    │   │
│  │  - 更新策略: 实时追加，会话结束清理                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Level 2: 短期记忆 (Short-Term Memory)                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - 存储位置: 内存 + 磁盘缓存                             │   │
│  │  - 容量限制: 最近 N 天/条记录 (可配置，默认100条)        │   │
│  │  - 保留时间: 7-30天 (可配置)                             │   │
│  │  - 存储内容: 近期会话摘要、高频访问记忆                  │   │
│  │  - 更新策略: LRU 淘汰，定期持久化                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Level 3: 长期记忆 (Long-Term Memory)                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - 存储位置: 向量数据库 (FAISS/Milvus) + 关系数据库      │   │
│  │  - 容量限制: 无限制 (受存储空间约束)                     │   │
│  │  - 保留时间: 永久 (直到主动删除或遗忘)                   │   │
│  │  - 存储内容: 所有历史对话、文档、知识、用户画像          │   │
│  │  - 更新策略: 异步写入，定期演化(遗忘/强化)               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 5.1.2 记忆存储流程详解

```python
class MemoryStorePipeline:
    """
    记忆存储流水线
    实现从原始输入到持久化存储的完整流程
    """

    async def store(self, event: UserEvent) -> MemoryEntry:
        """
        主存储流程
        """
        # Step 1: 内容预处理
        processed_content = await self.preprocess(event)

        # Step 2: 特征提取
        features = await self.extract_features(processed_content)

        # Step 3: 向量化
        embedding = await self.vectorize(processed_content)

        # Step 4: 元数据构建
        metadata = self.build_metadata(event, features)

        # Step 5: 可信度评估
        confidence = self.assess_confidence(event, features)

        # Step 6: 构建记忆条目
        entry = MemoryEntry(
            memory_id=generate_uuid(),
            user_id=event.user_id,
            content=processed_content.text,
            memory_type=self.classify_memory_type(event),
            embedding=embedding,
            confidence=confidence,
            importance=features.importance_score,
            tags=features.keywords,
            related_entities=features.entities,
            source=event.source,
        )

        # Step 7: 三级存储
        await self.tiered_store(entry)

        # Step 8: 更新关联图谱
        await self.update_relation_graph(entry)

        # Step 9: 触发用户画像学习
        await self.trigger_profile_learning(entry)

        return entry

    async def tiered_store(self, entry: MemoryEntry):
        """
        三级存储实现
        """
        # L1: 工作记忆 (同步写入，保证实时性)
        await self.working_memory.store(entry)

        # L2: 短期记忆 (异步写入)
        asyncio.create_task(self.short_term_memory.store(entry))

        # L3: 长期记忆 (批量异步写入)
        await self.long_term_memory.buffer(entry)
        if self.long_term_memory.buffer_size >= BATCH_SIZE:
            asyncio.create_task(self.long_term_memory.flush())

    def assess_confidence(self, event: UserEvent, features: Features) -> float:
        """
        可信度评估算法
        """
        confidence = 0.5  # 基础可信度

        # 来源可信度加权
        source_weights = {
            'user_explicit': 0.9,    # 用户明确陈述
            'user_implicit': 0.7,    # 用户隐含信息
            'inferred': 0.5,          # 推理得出
            'third_party': 0.6,       # 第三方来源
        }
        confidence *= source_weights.get(event.source_type, 0.5)

        # 实体识别置信度
        if features.entity_confidence > 0.8:
            confidence += 0.1

        # 上下文一致性检查
        if self.check_context_consistency(event, features):
            confidence += 0.1

        return min(confidence, 1.0)
```

### 5.2 记忆检索机制

#### 5.2.1 混合检索策略

```python
class HybridRetrievalEngine:
    """
    混合检索引擎
    整合多种检索策略，实现高召回率和高精度的平衡
    """

    async def retrieve(self, query: str, user_id: str,
                       context: QueryContext) -> List[RetrievalResult]:
        """
        混合检索主流程
        """
        # 并行执行多种检索
        tasks = [
            self.semantic_search(query, user_id),      # 语义检索
            self.keyword_search(query, user_id),       # 关键词检索
            self.graph_search(query, user_id),         # 图谱检索
            self.temporal_search(query, user_id),      # 时序检索
        ]

        results = await asyncio.gather(*tasks)

        # 结果融合
        fused = self.reciprocal_rank_fusion(results)

        # 个性化重排序
        reranked = await self.personalize_rerank(fused, user_id)

        # 时效性加权
        time_weighted = self.apply_temporal_weight(reranked)

        return time_weighted[:context.top_k]

    async def semantic_search(self, query: str, user_id: str) -> List[SearchResult]:
        """
        语义检索 - 基于向量相似度
        """
        # 生成查询向量
        query_embedding = await self.embedding_model.encode(query)

        # 向量数据库检索
        vector_results = await self.vector_db.search(
            vector=query_embedding,
            filter={"user_id": user_id},
            top_k=50
        )

        # 结果转换
        return [self.convert_vector_result(r) for r in vector_results]

    async def keyword_search(self, query: str, user_id: str) -> List[SearchResult]:
        """
        关键词检索 - 基于 BM25
        """
        # 中文分词
        tokens = jieba.lcut(query)
        tokens = [t for t in tokens if t not in stopwords]

        # BM25检索
        keyword_results = await self.text_search_engine.search(
            tokens=tokens,
            filter={"user_id": user_id},
            top_k=50
        )

        return [self.convert_keyword_result(r) for r in keyword_results]

    def reciprocal_rank_fusion(self, result_sets: List[List[SearchResult]],
                                k: int = 60) -> List[FusedResult]:
        """
        RRF 结果融合算法

        公式: score(d) = Σ(1 / (k + rank(d, result_set_i)))

        Args:
            result_sets: 多个检索结果集
            k: 平滑参数，通常取60
        """
        scores = defaultdict(float)

        for result_set in result_sets:
            for rank, result in enumerate(result_set, start=1):
                scores[result.memory_id] += 1.0 / (k + rank)

        # 按融合分数排序
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [self.load_full_result(mid, score)
                for mid, score in sorted_results]

    async def personalize_rerank(self, results: List[FusedResult],
                                  user_id: str) -> List[RetrievalResult]:
        """
        个性化重排序
        基于用户画像调整结果排序
        """
        profile = await self.user_profile_manager.get(user_id)

        reranked = []
        for result in results:
            # 基础分数
            score = result.fusion_score

            # 兴趣匹配度加分
            interest_match = self.calculate_interest_match(
                result, profile.interest_topics
            )
            score += interest_match * 0.2

            # 领域相关度加分
            if result.category in profile.expertise_areas:
                score += 0.1

            # 历史交互模式加分
            interaction_bonus = await self.get_interaction_bonus(
                user_id, result.memory_id
            )
            score += interaction_bonus

            reranked.append(RetrievalResult(
                memory=result,
                final_score=score
            ))

        return sorted(reranked, key=lambda x: x.final_score, reverse=True)
```

#### 5.2.2 检索流程图

```
用户查询
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 查询理解与扩展                                        │
│ - 意图识别 (查询 vs 记录)                                     │
│ - 实体提取与链接                                              │
│ - 查询扩展 (同义词/相关词)                                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ 语义检索分支    │ │ 关键词检索分支  │ │ 图谱检索分支    │
│                 │ │                 │ │                 │
│ 1. 查询向量化   │ │ 1. 查询分词     │ │ 1. 实体识别     │
│ 2. ANN搜索      │ │ 2. BM25计算     │ │ 2. 关系遍历     │
│ 3. 相似度排序   │ │ 3. 相关性排序   │ │ 3. 关联记忆召回 │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 结果融合 (RRF)                                        │
│ - 合并多源结果                                                │
│ - 消除重复                                                    │
│ - 计算融合分数                                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 个性化重排序                                          │
│ - 加载用户画像                                                │
│ - 计算兴趣匹配度                                              │
│ - 应用历史偏好                                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: 后处理与格式化                                        │
│ - 可信度过滤                                                  │
│ - 时效性加权                                                  │
│ - 结果摘要生成                                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                     返回检索结果
```

### 5.3 记忆管理机制

#### 5.3.1 记忆生命周期管理

```
记忆状态流转图:

┌─────────┐    创建     ┌─────────┐   访问/强化   ┌─────────┐
│  初始   │───────────▶│  活跃   │────────────▶│  强化   │
│  (New)  │            │ (Active)│              │(Reinforced)
└─────────┘            └────┬────┘              └────┬────┘
                            │                        │
                     长时间未访问              持续强化
                            │                        │
                            ▼                        ▼
                     ┌─────────────┐          ┌─────────────┐
                     │   衰退      │          │   核心记忆   │
                     │  (Decaying) │          │  (Core)     │
                     └──────┬──────┘          └─────────────┘
                            │
              权重低于阈值  │
                            ▼
                     ┌─────────────┐
                     │   归档      │
                     │ (Archived)  │
                     └──────┬──────┘
                            │
              超过保存期限  │
                            ▼
                     ┌─────────────┐
                     │   遗忘      │
                     │ (Forgotten) │
                     └─────────────┘
```

#### 5.3.2 记忆演化算法

```python
class MemoryEvolutionEngine:
    """
    记忆演化引擎
    实现记忆的动态遗忘与强化
    """

    def __init__(self):
        # 演化参数配置
        self.config = {
            'decay_rate': 0.05,           # 日衰减率
            'reinforcement_rate': 0.1,    # 强化率
            'forget_threshold': 0.15,     # 遗忘阈值
            'archive_threshold': 0.3,     # 归档阈值
            'core_threshold': 0.8,        # 核心记忆阈值
        }

    async def evolve_memory(self, memory: MemoryEntry):
        """
        单条记忆演化计算
        """
        days_inactive = (now() - memory.last_accessed).days

        # 1. 时间衰减计算
        # 使用指数衰减模型: weight = base * e^(-λt)
        decay_factor = math.exp(-self.config['decay_rate'] * days_inactive)

        # 2. 访问频率强化
        # 使用对数增长避免高频记忆无限增长
        access_boost = math.log1p(memory.access_count) * self.config['reinforcement_rate']

        # 3. 重要性基准
        base_importance = memory.importance

        # 4. 上下文关联度 (与当前热门话题的关联)
        relevance_boost = await self.calculate_relevance_boost(memory)

        # 5. 综合计算新权重
        new_weight = base_importance * decay_factor * (1 + access_boost) * (1 + relevance_boost)

        # 6. 边界处理
        new_weight = max(0.0, min(1.0, new_weight))

        # 7. 状态判定
        new_state = self.determine_state(new_weight, memory)

        return MemoryEvolution(
            memory_id=memory.memory_id,
            old_weight=memory.weight,
            new_weight=new_weight,
            old_state=memory.state,
            new_state=new_state,
            factors={
                'decay': decay_factor,
                'access_boost': access_boost,
                'relevance': relevance_boost,
            }
        )

    def determine_state(self, weight: float, memory: MemoryEntry) -> MemoryState:
        """
        根据权重判定记忆状态
        """
        if weight < self.config['forget_threshold']:
            return MemoryState.FORGOTTEN
        elif weight < self.config['archive_threshold']:
            return MemoryState.ARCHIVED
        elif weight > self.config['core_threshold'] and memory.access_count > 10:
            return MemoryState.CORE
        elif weight < memory.weight:  # 权重下降
            return MemoryState.DECAYING
        else:
            return MemoryState.ACTIVE

    async def batch_evolve(self, batch_size: int = 1000):
        """
        批量演化处理
        每日定时执行
        """
        offset = 0
        while True:
            # 分批获取待演化记忆
            memories = await self.memory_db.get_memories_for_evolution(
                limit=batch_size,
                offset=offset
            )

            if not memories:
                break

            # 并行计算演化
            evolutions = await asyncio.gather(*[
                self.evolve_memory(m) for m in memories
            ])

            # 应用演化结果
            for evolution in evolutions:
                await self.apply_evolution(evolution)

            offset += batch_size

    async def apply_evolution(self, evolution: MemoryEvolution):
        """
        应用演化结果
        """
        memory_id = evolution.memory_id

        # 更新权重
        await self.memory_db.update_weight(memory_id, evolution.new_weight)

        # 状态变更处理
        if evolution.new_state != evolution.old_state:
            await self.handle_state_transition(memory_id, evolution)

    async def handle_state_transition(self, memory_id: str,
                                       evolution: MemoryEvolution):
        """
        处理状态变更
        """
        new_state = evolution.new_state

        if new_state == MemoryState.FORGOTTEN:
            # 软删除或归档到冷存储
            await self.memory_db.soft_delete(memory_id)
            logger.info(f"Memory {memory_id} forgotten")

        elif new_state == MemoryState.ARCHIVED:
            # 迁移到归档存储
            await self.archive_memory(memory_id)
            logger.info(f"Memory {memory_id} archived")

        elif new_state == MemoryState.CORE:
            # 标记为核心记忆，提升存储优先级
            await self.memory_db.mark_as_core(memory_id)
            logger.info(f"Memory {memory_id} promoted to core")
```

---

## 六、用户画像与个性化设计

### 6.1 用户画像模型

#### 6.1.1 多维度画像架构

```
用户画像 (UserProfile)
│
├── 1. 基础属性层 (Basic Attributes)
│   ├── 用户ID、注册时间
│   ├── 设备信息、位置信息
│   └── 基本人口统计信息
│
├── 2. 偏好模型层 (Preference Model)
│   ├── 话题偏好 (Topic Preferences)
│   │   ├── 兴趣标签及权重
│   │   ├── 兴趣演化趋势
│   │   └── 季节性兴趣变化
│   │
│   ├── 交互偏好 (Interaction Preferences)
│   │   ├── 响应长度偏好
│   │   ├── 详细程度偏好
│   │   ├── 正式程度偏好
│   │   └── 主动建议接受度
│   │
│   └── 时间偏好 (Temporal Preferences)
│       ├── 活跃时段分布
│       ├── 响应延迟容忍度
│       └── 最佳交互时间窗口
│
├── 3. 行为模式层 (Behavior Patterns)
│   ├── 查询模式 (Query Patterns)
│   │   ├── 高频查询类型
│   │   ├── 查询时段分布
│   │   └── 查询链式特征
│   │
│   ├── 信息消费模式
│   │   ├── 阅读深度 (摘要 vs 全文)
│   │   ├── 多媒体偏好
│   │   └── 信息保存行为
│   │
│   └── 任务处理模式
│       ├── 任务完成率
│       ├── 常用工作流
│       └── 中断恢复习惯
│
├── 4. 知识领域层 (Knowledge Domain)
│   ├── 专业领域 (Expertise)
│   │   ├── 已确认的专业领域
│   │   ├── 知识深度评估
│   │   └── 知识更新频率
│   │
│   └── 学习轨迹 (Learning Trajectory)
│       ├── 新知识接受度
│       ├── 学习风格偏好
│       └── 近期学习重点
│
└── 5. 社交关系层 (Social Context)
    ├── 组织归属
    ├── 角色定位
    └── 协作网络特征
```

#### 6.1.2 画像数据模型

```python
@dataclass
class UserProfile:
    """用户画像主类"""

    user_id: str
    created_at: datetime
    updated_at: datetime

    # 偏好模型
    topic_preferences: List[TopicPreference]  # 话题偏好
    interaction_style: InteractionStyle        # 交互风格
    temporal_profile: TemporalProfile          # 时间特征

    # 行为统计
    behavior_stats: BehaviorStatistics         # 行为统计
    query_patterns: QueryPatternModel          # 查询模式

    # 知识领域
    expertise_areas: List[ExpertiseArea]       # 专业领域
    learning_profile: LearningProfile          # 学习特征

    # 记忆统计
    memory_stats: MemoryStatistics


@dataclass
class TopicPreference:
    """话题偏好"""
    topic: str                    # 话题标签
    weight: float                 # 偏好权重 (0-1)
    confidence: float             # 置信度
    first_seen: datetime          # 首次出现
    last_active: datetime         # 最近活跃
    trend: str                    # 趋势: 'rising', 'stable', 'declining'

    def update_weight(self, interaction: Interaction):
        """基于交互更新权重"""
        # 使用指数移动平均
        alpha = 0.1  # 学习率
        new_weight = self.weight * (1 - alpha) + interaction.interest_signal * alpha
        self.weight = new_weight


@dataclass
class InteractionStyle:
    """交互风格偏好"""

    # 响应长度偏好 (short/medium/long)
    preferred_response_length: str

    # 详细程度 (concise/balanced/detailed)
    preferred_detail_level: str

    # 正式程度 (casual/neutral/formal)
    preferred_formality: str

    # 主动性偏好 (reactive/balanced/proactive)
    proactivity_level: str

    # 情感表达偏好 (minimal/moderate/expressive)
    expressiveness: str


@dataclass
class TemporalProfile:
    """时间特征画像"""

    # 活跃时段分布 (24小时制，每小时活跃度0-1)
    hourly_activity_distribution: List[float]

    # 工作日 vs 周末模式
    weekday_pattern: ActivityPattern
    weekend_pattern: ActivityPattern

    # 响应时间特征
    avg_response_time: timedelta      # 平均响应延迟
    response_time_variability: float  # 响应时间变异度

    # 最佳交互窗口
    optimal_interaction_windows: List[TimeWindow]
```

### 6.2 用户画像学习机制

#### 6.2.1 画像学习流程

```
用户交互
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 特征提取                                              │
│ - 查询内容分析 (主题/意图/情感)                               │
│ - 交互行为分析 (响应时间/操作序列)                            │
│ - 反馈信号提取 (显式反馈/隐式反馈)                            │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 实时统计更新                                          │
│ - 更新访问频次                                                │
│ - 记录活跃时段                                                │
│ - 累计话题分布                                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 模式检测                                              │
│ - 检测新的兴趣点                                              │
│ - 识别行为模式变化                                            │
│ - 发现时间模式                                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
    ┌─────────────────┐             ┌─────────────────┐
    │ 增量更新        │             │ 触发批量学习    │
    │ (实时)          │             │ (定时/阈值)     │
    └────────┬────────┘             └────────┬────────┘
             │                               │
             ▼                               ▼
    ┌─────────────────┐             ┌─────────────────┐
    │ 更新偏好权重    │             │ 重新计算模式    │
    │ 调整时间窗口    │             │ 更新知识领域    │
    │ 记录新实体      │             │ 发现长期趋势    │
    └────────┬────────┘             └────────┬────────┘
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: 置信度评估                                            │
│ - 计算新发现的置信度                                          │
│ - 评估模式稳定性                                              │
│ - 识别需要确认的假设                                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: 画像持久化                                            │
│ - 更新画像数据库                                              │
│ - 触发记忆重索引 (如需)                                       │
│ - 生成画像变更日志                                            │
└─────────────────────────────────────────────────────────────┘
```

#### 6.2.2 画像学习算法

```python
class UserProfileLearner:
    """
    用户画像学习器
    实现从交互数据中自动学习用户特征
    """

    async def learn_from_interaction(self, user_id: str,
                                      interaction: UserInteraction):
        """
        从单次交互学习
        """
        # 1. 提取学习信号
        signals = self.extract_signals(interaction)

        # 2. 话题偏好学习
        await self.update_topic_preferences(user_id, signals.topic_signals)

        # 3. 交互风格学习
        await self.update_interaction_style(user_id, signals.style_signals)

        # 4. 时间模式学习
        await self.update_temporal_pattern(user_id, interaction.timestamp)

        # 5. 触发批量学习检查
        if await self.should_trigger_batch_learning(user_id):
            asyncio.create_task(self.batch_learn(user_id))

    async def update_topic_preferences(self, user_id: str,
                                        signals: List[TopicSignal]):
        """
        更新话题偏好
        使用指数移动平均实现平滑更新
        """
        profile = await self.profile_manager.get(user_id)

        for signal in signals:
            topic = signal.topic
            strength = signal.strength  # 0-1

            # 查找或创建话题偏好
            pref = profile.get_topic_preference(topic)
            if not pref:
                pref = TopicPreference(topic=topic, weight=0.5)
                profile.topic_preferences.append(pref)

            # 指数移动平均更新
            alpha = 0.1  # 学习率，可根据置信度调整
            old_weight = pref.weight
            new_weight = old_weight * (1 - alpha) + strength * alpha

            pref.weight = new_weight
            pref.last_active = now()
            pref.confidence = min(pref.confidence + 0.01, 1.0)

            # 计算趋势
            if new_weight > old_weight * 1.1:
                pref.trend = 'rising'
            elif new_weight < old_weight * 0.9:
                pref.trend = 'declining'
            else:
                pref.trend = 'stable'

        await self.profile_manager.update(profile)

    async def batch_learn(self, user_id: str):
        """
        批量学习 - 深度分析用户历史数据
        定期执行或积累足够数据后触发
        """
        # 1. 加载用户历史数据
        history = await self.load_interaction_history(user_id, days=30)

        # 2. 查询模式挖掘
        query_patterns = self.mine_query_patterns(history)

        # 3. 时间模式分析
        temporal_patterns = self.analyze_temporal_patterns(history)

        # 4. 知识领域推断
        expertise_areas = self.infer_expertise_areas(history)

        # 5. 更新画像
        profile = await self.profile_manager.get(user_id)
        profile.query_patterns = query_patterns
        profile.temporal_profile = temporal_patterns
        profile.expertise_areas = expertise_areas

        await self.profile_manager.update(profile)

    def mine_query_patterns(self, history: List[UserInteraction]) -> QueryPatternModel:
        """
        挖掘查询模式
        使用序列模式挖掘算法
        """
        # 统计查询类型分布
        type_distribution = Counter(i.query_type for i in history)

        # 识别高频查询链
        sequences = []
        current_sequence = []
        for interaction in history:
            if interaction.type == 'query':
                current_sequence.append(interaction.query_intent)
            else:
                if len(current_sequence) > 1:
                    sequences.append(tuple(current_sequence))
                current_sequence = []

        frequent_sequences = self.find_frequent_sequences(sequences, min_support=3)

        # 分析时段分布
        hourly_distribution = [0] * 24
        for interaction in history:
            hour = interaction.timestamp.hour
            hourly_distribution[hour] += 1

        return QueryPatternModel(
            type_distribution=type_distribution,
            frequent_sequences=frequent_sequences,
            hourly_distribution=hourly_distribution,
        )

    def analyze_temporal_patterns(self, history: List[UserInteraction]) -> TemporalProfile:
        """
        分析时间模式
        """
        # 计算每小时的活跃度
        hourly_counts = [0] * 24
        for interaction in history:
            hour = interaction.timestamp.hour
            hourly_counts[hour] += 1

        # 归一化
        total = sum(hourly_counts)
        hourly_distribution = [c / total for c in hourly_counts]

        # 识别活跃窗口
        windows = self.extract_active_windows(hourly_distribution, threshold=0.05)

        # 计算响应时间特征
        response_times = [i.response_time for i in history if i.response_time]
        avg_response_time = sum(response_times, timedelta()) / len(response_times)

        return TemporalProfile(
            hourly_activity_distribution=hourly_distribution,
            optimal_interaction_windows=windows,
            avg_response_time=avg_response_time,
        )
```

### 6.3 个性化记忆召回

#### 6.3.1 个性化检索增强

```python
class PersonalizedRetrieval:
    """
    个性化记忆检索
    将用户画像融入检索过程
    """

    async def personalized_search(self, query: str, user_id: str) -> List[MemoryEntry]:
        """
        个性化搜索主流程
        """
        # 1. 加载用户画像
        profile = await self.profile_manager.get(user_id)

        # 2. 查询扩展 (基于用户画像)
        expanded_queries = self.expand_query(query, profile)

        # 3. 执行多查询检索
        all_results = []
        for eq in expanded_queries:
            results = await self.retrieval_engine.retrieve(eq, user_id)
            all_results.extend(results)

        # 4. 个性化重排序
        reranked = self.personalize_rank(all_results, profile, query)

        # 5. 多样性保证
        diverse_results = self.ensure_diversity(reranked, profile)

        return diverse_results

    def expand_query(self, query: str, profile: UserProfile) -> List[str]:
        """
        基于用户画像的查询扩展
        """
        expanded = [query]  # 原始查询

        # 根据话题偏好扩展同义词
        query_topics = self.extract_topics(query)
        for topic in query_topics:
            if pref := profile.get_topic_preference(topic):
                if pref.weight > 0.7:  # 用户熟悉的话题
                    # 添加相关术语
                    related_terms = self.get_related_terms(topic)
                    for term in related_terms:
                        expanded.append(query.replace(topic, term))

        # 根据历史查询模式补全
        similar_queries = profile.query_patterns.find_similar(query)
        expanded.extend([sq for sq, score in similar_queries if score > 0.8])

        return list(set(expanded))[:5]  # 最多5个扩展查询

    def personalize_rank(self, results: List[RetrievalResult],
                         profile: UserProfile,
                         query: str) -> List[RetrievalResult]:
        """
        个性化重排序
        """
        scored_results = []

        for result in results:
            base_score = result.score

            # 话题匹配加分
            topic_match_score = self.calculate_topic_match(
                result.memory, profile.topic_preferences
            )

            # 领域相关加分
            expertise_bonus = 0.0
            if result.memory.category in [e.domain for e in profile.expertise_areas]:
                expertise_bonus = 0.1

            # 时效性偏好
            time_relevance = self.calculate_time_relevance(
                result.memory, profile.temporal_profile
            )

            # 历史交互偏好
            interaction_bonus = self.get_historical_preference(
                profile.user_id, result.memory.memory_id
            )

            # 综合评分
            final_score = (
                base_score * 0.4 +
                topic_match_score * 0.3 +
                expertise_bonus +
                time_relevance * 0.1 +
                interaction_bonus * 0.1
            )

            scored_results.append((result, final_score))

        # 按最终分数排序
        scored_results.sort(key=lambda x: x[1], reverse=True)

        return [r for r, s in scored_results]

    def ensure_diversity(self, results: List[MemoryEntry],
                         profile: UserProfile) -> List[MemoryEntry]:
        """
        保证结果多样性
        避免过度个性化导致的过滤气泡
        """
        diverse_results = []
        topic_coverage = set()

        for result in results:
            result_topics = set(result.tags)

            # 如果新话题覆盖率高，优先保留
            new_coverage = result_topics - topic_coverage
            if len(new_coverage) > 0 or len(diverse_results) < 3:
                diverse_results.append(result)
                topic_coverage.update(result_topics)

            if len(diverse_results) >= 10:
                break

        return diverse_results
```

### 6.4 AI理解用户的反馈闭环

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户理解反馈闭环                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐                                                  │
│   │ 用户交互  │                                                  │
│   └────┬─────┘                                                  │
│        │                                                        │
│        ▼                                                        │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│   │ 意图理解  │────▶│ 检索记忆  │────▶│ 生成响应  │               │
│   └──────────┘     └──────────┘     └────┬─────┘               │
│                                          │                      │
│                                          ▼                      │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│   │ 画像更新  │◀────│ 信号提取  │◀────│ 用户反馈  │               │
│   └────┬─────┘     └──────────┘     └────┬─────┘               │
│        │                                 │                      │
│        │         ┌──────────┐          │                      │
│        └────────▶│ 理解深化  │◀─────────┘                      │
│                  └──────────┘                                   │
│                       │                                         │
│                       ▼                                         │
│                  ┌──────────┐                                   │
│                  │ 下一轮交互 │                                  │
│                  └──────────┘                                   │
│                                                                 │
│  反馈信号类型:                                                   │
│  - 显式: 点赞/点踩、收藏、明确纠正                               │
│  - 隐式: 响应时间、是否追问、是否采纳建议、会话是否继续          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 七、总结与展望

### 7.1 核心技术创新

| 创新点 | 技术方案 | 预期效果 |
|--------|----------|----------|
| **分层记忆架构** | 工作/短期/长期三级记忆 | 平衡实时性与持久性 |
| **混合检索引擎** | 稠密+稀疏+图谱+时序 | 高召回率+高精度 |
| **记忆演化机制** | 自动遗忘与强化 | 保持记忆时效性 |
| **动态用户画像** | 实时学习+批量挖掘 | 深度理解用户 |
| **个性化召回** | 画像增强检索 | 千人千面的体验 |

### 7.2 技术选型

| 模块 | 技术方案 | 理由 |
|------|----------|------|
| 向量数据库 | FAISS/Milvus | 高效ANN搜索 |
| 关系数据库 | SQLite/PostgreSQL | 元数据管理 |
| 嵌入模型 | BGE-M3 | 多语言支持 |
| 重排序 | bge-reranker | 精度提升 |
| LLM | GPT-4/Claude/Qwen | 语义理解 |
| 分词 | Jieba | 中文优化 |

### 7.3 后续规划

1. **第一阶段** (已完成): 基础架构设计、核心模块规划
2. **第二阶段** (进行中): 记忆存储与检索实现
3. **第三阶段** (计划中): 用户画像系统开发
4. **第四阶段** (计划中): 记忆演化引擎实现
5. **第五阶段** (计划中): 系统集成与测试

---

*本文档为智忆助理项目中期汇报材料，包含完整的系统设计、流程图和详细技术方案。*
