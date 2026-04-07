# 智忆助理 (MemoryMate) - 系统图表集合

> 本文件包含所有系统设计的Mermaid图表代码，可在支持Mermaid的编辑器或网页中渲染

---

## 1. 系统总体架构图

```mermaid
graph TB
    subgraph 交互层[交互层 Interface Layer]
        A1[聊天接口]
        A2[语音接口]
        A3[Web界面]
        A4[第三方API集成<br/>日程/邮件/文档]
    end

    subgraph 认知层[认知层 Cognition Layer]
        subgraph 核心智能体[核心智能体引擎]
            B1[意图理解模块]
            B2[任务规划模块]
            B3[响应生成模块]
        end

        subgraph 记忆引擎[记忆管理引擎]
            C1[工作记忆<br/>当前会话]
            C2[短期记忆<br/>近期历史]
            C3[长期记忆<br/>永久存储]
            C4[用户画像<br/>建模]
        end
    end

    subgraph 存储层[存储层 Storage Layer]
        D1[(向量数据库<br/>FAISS/Milvus)]
        D2[(关系数据库<br/>SQLite/PostgreSQL)]
        D3[对象存储<br/>文件系统]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1

    B1 --> B2
    B2 --> B3

    B1 --> C1
    C1 --> C2
    C2 --> C3
    C3 --> C4

    C1 -.-> D2
    C2 -.-> D2
    C3 -.-> D1
    C3 -.-> D2
    C4 -.-> D2
    D1 -.-> D3
```

---

## 2. 数据流向图

```mermaid
flowchart LR
    A[用户输入] --> B[多模态解析]
    B --> C[实体识别]
    C --> D[意图分类]

    D --> E{意图类型}
    E -->|查询| F[记忆检索引擎]
    E -->|记录| G[记忆存储引擎]
    E -->|交互| H[上下文构建]

    F --> I[结果融合]
    G --> I
    H --> I

    I --> J[记忆融合]
    J --> K[用户画像增强]
    K --> L[响应生成]
    L --> M[用户输出]
```

---

## 3. 记忆存储流程活动图

```mermaid
flowchart TD
    Start([开始]) --> A[接收用户输入]
    A --> B[多模态解析]
    B --> C[实体识别]
    C --> D[意图分类]
    D --> E[存入工作记忆]

    E --> F[提取记忆特征]
    F --> G[生成向量嵌入]
    G --> H[可信度评估]
    H --> I{可信度?}

    I -->|低| J[标记待验证]
    I -->|高| K[更新用户画像]

    J --> L[异步持久化]
    K --> L

    L --> M[更新关联图谱]
    M --> N([结束])
```

---

## 4. 记忆检索流程活动图

```mermaid
flowchart TD
    Start([开始]) --> A[接收查询]
    A --> B[查询理解]
    B --> C[实体链接]

    C --> D{并行检索}
    D --> E[语义检索]
    D --> F[关键词检索]
    D --> G[图谱检索]
    D --> H[时序检索]

    E --> I[RRF结果融合]
    F --> I
    G --> I
    H --> I

    I --> J[时效性过滤]
    J --> K[个性化重排序]
    K --> L[可信度筛选]
    L --> M[返回结果]
    M --> End([结束])
```

---

## 5. 三级记忆架构图

```mermaid
graph TB
    subgraph 工作记忆[工作记忆 Working Memory]
        WM1[当前对话上下文]
        WM2[临时实体缓存]
        WM3[会话状态]
    end

    subgraph 短期记忆[短期记忆 Short-Term Memory]
        STM1[近期会话摘要]
        STM2[高频访问记忆]
        STM3[待处理队列]
    end

    subgraph 长期记忆[长期记忆 Long-Term Memory]
        LTM1[(语义记忆<br/>向量存储)]
        LTM2[(情景记忆<br/>关系数据库)]
        LTM3[(程序记忆<br/>知识图谱)]
    end

    subgraph 演化机制[记忆演化机制]
        E1[时间衰减]
        E2[访问强化]
        E3[主动遗忘]
    end

    WM1 -.->|定期聚合| STM1
    STM1 -.->|重要记忆| LTM1
    STM1 -.->|完整记录| LTM2

    LTM1 -.-> E1
    LTM2 -.-> E2
    LTM3 -.-> E3
```

---

## 6. 混合检索架构图

```mermaid
graph LR
    Q[用户查询] --> QE[查询扩展]
    QE --> QV[查询向量化]

    QV --> D1[稠密检索]
    QE --> S1[稀疏检索]
    QE --> G1[图谱检索]

    D1 --> VDB[(向量数据库<br/>FAISS)]
    S1 --> TSE[文本搜索引擎<br/>BM25]
    G1 --> KG[(知识图谱)]

    VDB --> RF[RRF融合层]
    TSE --> RF
    KG --> RF

    RF --> PR[个性化重排序]
    PR --> UP[(用户画像)]

    PR --> TF[时效性过滤]
    TF --> RESULT[检索结果]
```

---

## 7. 用户画像模型图

```mermaid
mindmap
  root((用户画像))
    基础属性
      用户ID
      注册时间
      设备信息
      位置信息
    偏好模型
      话题偏好
        兴趣标签权重
        兴趣演化趋势
      交互偏好
        响应长度偏好
        详细程度偏好
        主动建议接受度
      时间偏好
        活跃时段分布
        响应延迟容忍度
    行为模式
      查询模式
        高频查询类型
        查询链式特征
      信息消费模式
        阅读深度偏好
        多媒体偏好
    知识领域
      专业领域
        已确认领域
        知识深度
      学习轨迹
        新知识接受度
        近期学习重点
    记忆统计
      总记忆数
      交互频次
      遗忘率
```

---

## 8. 记忆演化状态机

```mermaid
stateDiagram-v2
    [*] --> 初始: 创建记忆
    初始 --> 活跃: 权重>阈值

    活跃 --> 强化: 频繁访问
    强化 --> 核心记忆: 权重>0.8且访问>10

    活跃 --> 衰退: 长时间未访问
    衰退 --> 活跃: 重新访问

    衰退 --> 归档: 权重<0.3
    归档 --> [*]: 超期删除

    核心记忆 --> 归档: 权重下降
    核心记忆 --> 活跃: 保持访问

    初始 --> 遗忘: 可信度极低
    衰退 --> 遗忘: 权重<0.15
    遗忘 --> [*]: 物理删除
```

---

## 9. 用户画像学习流程图

```mermaid
sequenceDiagram
    participant U as 用户
    participant I as 交互接口
    participant F as 特征提取器
    participant L as 画像学习器
    participant P as 画像数据库

    U->>I: 发送消息/查询
    I->>F: 提取交互特征
    F->>F: 主题分析
    F->>F: 情感分析
    F->>F: 行为模式识别
    F->>L: 学习信号

    L->>L: 更新话题偏好
    L->>L: 调整交互风格
    L->>L: 学习时间模式

    alt 触发批量学习
        L->>L: 深度模式挖掘
        L->>L: 知识领域推断
    end

    L->>P: 保存画像更新
    P-->>L: 确认
```

---

## 10. 个性化检索流程时序图

```mermaid
sequenceDiagram
    participant U as 用户
    participant A as Agent核心
    participant R as 检索引擎
    participant P as 画像管理器
    participant V as 向量数据库
    participant T as 文本搜索引擎

    U->>A: 提交查询
    A->>P: 获取用户画像
    P-->>A: 返回画像数据

    A->>A: 查询扩展
    Note over A: 基于话题偏好<br/>扩展同义词和相关词

    par 并行检索
        A->>V: 语义检索
        V-->>A: 向量相似结果
    and
        A->>T: 关键词检索
        T-->>A: BM25结果
    end

    A->>A: RRF结果融合
    A->>A: 个性化重排序
    Note over A: 话题匹配+领域相关<br/>+历史偏好+时效性

    A->>A: 多样性保证
    A-->>U: 返回个性化结果
```

---

## 11. 模块依赖关系图

```mermaid
graph TB
    subgraph 核心模块[核心模块]
        Core[Agent核心]
        MM[记忆管理器]
        UP[用户画像管理器]
    end

    subgraph 引擎层[引擎层]
        RE[检索引擎]
        SE[存储引擎]
        EE[演化引擎]
        LE[学习引擎]
    end

    subgraph 基础层[基础层]
        VS[向量存储]
        MS[元数据存储]
        FS[文件存储]
        EM[嵌入模型]
    end

    Core --> MM
    Core --> UP

    MM --> RE
    MM --> SE
    MM --> EE

    UP --> LE

    RE --> VS
    RE --> MS
    RE --> EM

    SE --> VS
    SE --> MS
    SE --> FS

    EE --> MS

    LE --> MS

    EM -.-> VS
```

---

## 12. 系统部署架构图

```mermaid
graph TB
    subgraph 客户端[客户端层]
        Web[Web界面]
        Mobile[移动App]
        Desktop[桌面客户端]
    end

    subgraph API网关[API网关层]
        Gateway[API Gateway]
        Auth[认证服务]
        RateLimit[限流服务]
    end

    subgraph 服务层[服务层]
        AgentService[Agent服务<br/>多实例]
        MemoryService[记忆服务<br/>多实例]
        UserService[用户服务<br/>多实例]
    end

    subgraph 数据层[数据层]
        VectorDB[(向量数据库集群<br/>Milvus)]
        MetaDB[(元数据库主从<br/>PostgreSQL)]
        Cache[(缓存层<br/>Redis)]
        ObjectStore[(对象存储<br/>MinIO/S3)]
    end

    Web --> Gateway
    Mobile --> Gateway
    Desktop --> Gateway

    Gateway --> Auth
    Gateway --> RateLimit

    Gateway --> AgentService
    Gateway --> MemoryService
    Gateway --> UserService

    AgentService --> MemoryService
    AgentService --> UserService

    MemoryService --> VectorDB
    MemoryService --> MetaDB
    MemoryService --> Cache
    MemoryService --> ObjectStore

    UserService --> MetaDB
    UserService --> Cache
```

---

## 如何使用这些图表

### 方法1: VS Code + 插件
1. 安装 "Markdown Preview Mermaid Support" 或 "Mermaid Preview" 插件
2. 打开本文件即可预览图表

### 方法2: Mermaid Live Editor
1. 访问 https://mermaid.live/
2. 复制对应的Mermaid代码
3. 粘贴到编辑器中实时渲染

### 方法3: 导出为图片
在Mermaid Live Editor中点击 "Actions" -> "PNG/SVG" 导出

### 方法4: Markdown渲染器
许多现代Markdown渲染器支持Mermaid，如：
- GitHub/GitLab (原生支持)
- Notion (通过代码块)
- Typora
- Obsidian + 插件

---

*本文档配合《智忆助理详细设计文档》使用，提供可视化的系统架构参考。*
