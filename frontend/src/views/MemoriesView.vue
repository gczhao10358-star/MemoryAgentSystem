<template>
  <div class="memories-view">
    <div class="view-header">
      <div class="view-header-copy">
        <div class="title">
          <el-icon><Collection /></el-icon>
          <span>记忆库</span>
        </div>
        <div class="subtitle">浏览已经沉淀下来的长期记忆和结构化信息。</div>
      </div>
      <div class="search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索记忆..."
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch">
              <el-icon><Search /></el-icon>
            </el-button>
          </template>
        </el-input>
      </div>
    </div>

    <div class="memories-content">
      <div class="memory-overview">
        <div class="overview-card">
          <div class="overview-label">记忆总数</div>
          <div class="overview-value">{{ memoryStore.memories.length }}</div>
        </div>
        <div class="overview-card">
          <div class="overview-label">当前结果</div>
          <div class="overview-value">{{ filteredMemories.length }}</div>
        </div>
        <div class="overview-card">
          <div class="overview-label">搜索状态</div>
          <div class="overview-value small">{{ searchQuery.trim() ? '已过滤' : '全部' }}</div>
        </div>
      </div>

      <el-empty v-if="!memoryStore.isLoading && filteredMemories.length === 0" description="暂无记忆" />

      <div v-else class="memories-list">
        <el-card
          v-for="memory in filteredMemories"
          :key="memory.memory_id"
          class="memory-card"
          shadow="hover"
        >
          <div class="memory-header">
            <el-tag :type="getTagType(memory.memory_type)" effect="dark" round>
              {{ getTypeLabel(memory.memory_type) }}
            </el-tag>
            <div class="memory-score">
              <el-icon><StarFilled /></el-icon>
              {{ (memory.confidence * 100).toFixed(0) }}%
            </div>
          </div>

          <div class="memory-content">{{ memory.content }}</div>

          <div class="memory-footer">
            <span>
              <el-icon><Calendar /></el-icon>
              {{ formatDate(memory.created_at) }}
            </span>
            <span>
              <el-icon><Lightning /></el-icon>
              {{ memory.importance.toFixed(2) }}
            </span>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  Collection, Search, StarFilled, Calendar, Lightning
} from '@element-plus/icons-vue'
import { useMemoryStore } from '@/stores/memory'

const memoryStore = useMemoryStore()
const searchQuery = ref('')

const filteredMemories = computed(() => {
  let memories = memoryStore.memories.filter(memory => memory.memory_type !== 'chat')

  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    memories = memories.filter(m =>
      m.content.toLowerCase().includes(query)
    )
  }

  return memories
})

const typeMap = {
  fact: { label: '事实', type: 'primary' },
  event: { label: '事件', type: 'warning' },
  task: { label: '任务', type: 'danger' },
  reminder: { label: '提醒', type: 'info' },
  document: { label: '文档', type: '' }
}

function getTypeLabel(type) {
  return typeMap[type]?.label || type
}

function getTagType(type) {
  return typeMap[type]?.type || ''
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

function handleSearch() {
  // 本地搜索已在前端实现
}

onMounted(() => {
  memoryStore.loadMemories()
})
</script>

<style scoped lang="scss">
.memories-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 20%),
    linear-gradient(180deg, #07111f 0%, #0b1324 50%, #0a1423 100%);
}

.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 24px;
  background: rgba(8, 18, 34, 0.78);
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.18);
  backdrop-filter: blur(18px);
}

.view-header-copy {
  min-width: 0;

  .title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 20px;
    font-weight: 700;
    color: #eef6ff;

    .el-icon {
      color: #5eead4;
    }
  }
}

.subtitle {
  margin-top: 6px;
  color: #8ea3bf;
  font-size: 13px;
}

.search-box {
  width: 300px;

:deep(.el-input__wrapper) {
    background: rgba(51, 65, 85, 0.5);
    box-shadow: none;
    border: 1px solid #475569;

    &.is-focus {
      border-color: #6366f1;
    }
  }

:deep(.el-input__inner) {
    color: #f1f5f9;

    &::placeholder {
      color: #64748b;
    }
  }
}

.memories-content {
  flex: 1;
  overflow-y: auto;
  padding: 4px 2px 20px;
}

.memory-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.overview-card {
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(127, 156, 191, 0.14);
  background: rgba(8, 18, 34, 0.7);
  box-shadow: 0 16px 32px rgba(2, 6, 23, 0.14);
}

.overview-label {
  color: #7f93ad;
  font-size: 12px;
}

.overview-value {
  margin-top: 10px;
  color: #f1f7ff;
  font-size: 28px;
  font-weight: 700;
}

.overview-value.small {
  font-size: 18px;
}

.memories-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 18px;
}

.memory-card {
  background: linear-gradient(180deg, rgba(13, 24, 40, 0.92) 0%, rgba(10, 19, 33, 0.88) 100%);
  border: 1px solid rgba(127, 156, 191, 0.14);
  transition: all 0.3s ease;
  border-radius: 22px;

  &:hover {
    border-color: rgba(94, 234, 212, 0.32);
    transform: translateY(-2px);
    box-shadow: 0 22px 40px rgba(2, 6, 23, 0.18);
  }

  :deep(.el-card__body) {
    padding: 18px;
  }
}

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.memory-score {
  font-size: 13px;
  color: #9db0c8;

  .el-icon {
    color: #fbbf24;
    margin-right: 4px;
  }
}

.memory-content {
  font-size: 14px;
  line-height: 1.6;
  color: #eef6ff;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.memory-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #6f88a7;

  span {
    display: flex;
    align-items: center;
    gap: 4px;

    .el-icon {
      font-size: 14px;
    }
  }
}

@media (max-width: 960px) {
  .memories-view {
    padding: 12px;
    gap: 12px;
  }

  .view-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .search-box {
    width: 100%;
  }

  .memory-overview {
    grid-template-columns: 1fr;
  }

  .memories-list {
    grid-template-columns: 1fr;
  }
}
</style>
