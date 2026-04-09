<template>
  <div class="memories-view">
    <div class="view-header">
      <div class="title">
        <el-icon><Collection /></el-icon>
        <span>记忆库</span>
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
      <el-empty v-if="!memoryStore.isLoading && filteredMemories.length === 0" description="暂无记忆" />

      <div v-else class="memories-list">
        <el-card
          v-for="memory in filteredMemories"
          :key="memory.memory_id"
          class="memory-card"
          shadow="hover"
        >
          <div class="memory-header">
            <el-tag :type="getTagType(memory.memory_type)" effect="dark">
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
  let memories = memoryStore.memories

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
  chat: { label: '对话', type: 'success' },
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
}

.view-header {
  padding: 20px 24px;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1e293b;

  .title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 20px;
    font-weight: 600;

    .el-icon {
      color: #6366f1;
    }
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
}

.memories-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #0f172a;
}

.memories-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.memory-card {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;
  transition: all 0.3s ease;

  &:hover {
    border-color: #6366f1;
    transform: translateY(-2px);
  }

  :deep(.el-card__body) {
    padding: 16px;
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
  color: #94a3b8;

  .el-icon {
    color: #fbbf24;
    margin-right: 4px;
  }
}

.memory-content {
  font-size: 14px;
  line-height: 1.6;
  color: #f1f5f9;
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
  color: #64748b;

  span {
    display: flex;
    align-items: center;
    gap: 4px;

    .el-icon {
      font-size: 14px;
    }
  }
}
</style>
