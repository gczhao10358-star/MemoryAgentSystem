# Memory Architecture

## Current Model

项目当前建议使用一套更简单、可演进的记忆模型，而不是严格的“三级记忆”：

- `session memory`
  负责当前会话线程的上下文窗口。
  以 `user_id + session_id` 为隔离键，保存最近若干轮对话。
- `durable memory`
  负责真正需要长期保留和检索的记忆。
  持久化到 SQLite 元数据和向量索引，支持结构化字段、检索、演化。
- `pinned view`
  不是独立存储层。
  它是从 `durable memory` 中动态筛出来的高重要度、高访问频次或特定类型记忆，用于在提示词中稳定注入核心信息。

## Why Not Three Layers

“工作记忆 / 短期记忆 / 长期记忆”这套模型在概念上容易重叠：

- 工作记忆和会话上下文本质上是一件事。
- 短期记忆如果同时承担“缓存”和“业务记忆”，边界会变得模糊。
- 长期记忆通常才是真正需要治理、检索和演化的对象。

所以当前实现把它收敛为：

- 会话上下文：`session memory`
- 性能优化层：`memory cache`
- 业务真相源：`durable memory`

其中 `memory cache` 只是 `durable memory` 的加速层，不单独承担产品语义。

## Current Mapping In Code

- `MemoryManager.session_memory`
  当前对话上下文
- `MemoryManager.memory_cache`
  近期热点缓存
- `MemoryManager.durable_memory`
  持久记忆存储入口

为了兼容旧代码，目前仍保留以下旧别名：

- `working_memory`
- `short_term_memory`
- `long_term_memory`

## Session Model

- `user_id`
  用户身份
- `session_id`
  一条连续对话线程
- `turn_id`
  一轮用户消息和助手回复的关联标识

推荐规则：

- 新建话题时创建新的 `session_id`
- 同一话题持续追问时复用同一个 `session_id`
- 每次用户发言生成新的 `turn_id`

## Retrieval Assembly

一次对话生成时，推荐上下文拼装顺序：

1. `session memory`
2. `pinned view`
3. `durable memory` 检索结果

这样能优先保证线程连贯性，再补充用户稳定画像和高价值事实，最后再引入与当前 query 强相关的历史记忆。

## Migration Notes

- 配置层推荐使用 `session_memory` 和 `memory_cache`
- 旧配置 `working_memory` / `short_term_memory` 仍兼容
- 统计字段推荐使用 `session_turns` / `cache_entries`
- 旧字段 `working_memory_turns` / `short_term_entries` 仍保留用于兼容
