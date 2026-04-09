<template>
  <div class="stats-view">
    <div class="view-header">
      <div class="title">
        <el-icon><TrendCharts /></el-icon>
        <span>数据统计</span>
      </div>
      <el-button type="primary" plain @click="refreshStats">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <div class="stats-content">
      <div class="stats-grid">
        <el-card class="stat-card" shadow="hover">
          <el-icon size="32" color="#6366f1"><Collection /></el-icon>
          <div class="stat-value">{{ stats.memory?.total_memories || 0 }}</div>
          <div class="stat-label">总记忆数</div>
        </el-card>

        <el-card class="stat-card" shadow="hover">
          <el-icon size="32" color="#10b981"><ChatRound /></el-icon>
          <div class="stat-value">{{ stats.memory?.working_memory_turns || 0 }}</div>
          <div class="stat-label">对话轮次</div>
        </el-card>

        <el-card class="stat-card" shadow="hover">
          <el-icon size="32" color="#f59e0b"><Briefcase /></el-icon>
          <div class="stat-value">{{ stats.memory?.short_term_entries || 0 }}</div>
          <div class="stat-label">短期记忆</div>
        </el-card>

        <el-card class="stat-card" shadow="hover">
          <el-icon size="32" color="#ec4899"><StarFilled /></el-icon>
          <div class="stat-value">{{ avgConfidence }}</div>
          <div class="stat-label">平均可信度</div>
        </el-card>
      </div>

      <div class="stats-row">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="chart-header">
              <span>记忆类型分布</span>
            </div>
          </template>

          <div v-if="memoryTypeData.length > 0" class="type-distribution">
            <div
              v-for="item in memoryTypeData"
              :key="item.name"
              class="type-item"
            >
              <div class="type-info">
                <span class="type-name">{{ item.name }}</span>
                <span class="type-count">{{ item.value }}</span>
              </div>
              <div class="type-bar">
                <div
                  class="type-bar-fill"
                  :style="{ width: item.percentage + '%', backgroundColor: item.color }"
                ></div>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>

        <el-card class="profile-card" shadow="hover">
          <template #header>
            <div class="chart-header">
              <span>用户画像</span>
            </div>
          </template>

          <div v-if="profileData.topic_count > 0" class="profile-content">
            <div class="profile-section">
              <h4>话题偏好 ({{ profileData.topic_count }})</h4>
              <div class="topic-tags">
                <el-tag
                  v-for="topic in profileData.top_topics"
                  :key="topic.topic"
                  :type="getTopicTagType(topic.weight)"
                  class="topic-tag"
                  effect="dark"
                >
                  {{ topic.topic }}
                  <span class="topic-weight">({{ (topic.weight * 100).toFixed(0) }}%)</span>
                </el-tag>
              </div>
            </div>

            <div class="profile-section" v-if="profileData.expertise_count > 0">
              <h4>专业领域</h4>
              <div class="expertise-list">
                <el-tag
                  v-for="exp in profileData.expertise_areas"
                  :key="exp.domain"
                  :type="getExpertiseTagType(exp.level)"
                  class="expertise-tag"
                  effect="dark"
                >
                  {{ exp.domain }}
                  <span class="expertise-level">({{ getExpertiseLevelLabel(exp.level) }})</span>
                </el-tag>
              </div>
            </div>

            <div class="profile-section">
              <h4>交互统计</h4>
              <div class="interaction-stats">
                <div class="stat-item">
                  <span class="stat-label">总交互:</span>
                  <span class="stat-value">{{ profileData.total_interactions || 0 }}</span>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无画像数据，多和我聊聊吧！" />
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { TrendCharts, Refresh, Collection, ChatRound, Briefcase, StarFilled } from '@element-plus/icons-vue'
import { useStatsStore } from '@/stores/stats'
import { useUserStore } from '@/stores/user'

const statsStore = useStatsStore()
const userStore = useUserStore()

const stats = computed(() => statsStore.stats)

// 监听用户ID变化，当用户登录后自动加载统计
watch(() => userStore.userId, (newUserId) => {
  if (newUserId) {
    console.log('[StatsView] 检测到用户登录，加载统计数据:', newUserId)
    statsStore.loadStats()
  }
}, { immediate: true })

const avgConfidence = computed(() => {
  const confidence = stats.value.memory?.avg_confidence || 0
  return confidence.toFixed(2)
})

const memoryTypeData = computed(() => {
  const memories = stats.value.memory?.memory_types || {}
  const typeMap = {
    fact: '事实',
    chat: '对话',
    event: '事件',
    task: '任务',
    reminder: '提醒',
    document: '文档'
  }
  const colors = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#0ea5e9']

  const data = Object.entries(memories).map(([type, count], index) => ({
    name: typeMap[type] || type,
    value: count,
    color: colors[index % colors.length]
  }))

  const total = data.reduce((sum, item) => sum + item.value, 0)
  data.forEach(item => {
    item.percentage = total > 0 ? (item.value / total) * 100 : 0
  })

  return data.sort((a, b) => b.value - a.value)
})

const profileData = computed(() => {
  return stats.value.profile || {}
})

function getTopicTagType(weight) {
  if (weight >= 0.8) return 'danger'
  if (weight >= 0.6) return 'warning'
  if (weight >= 0.4) return 'success'
  return 'info'
}

function getExpertiseTagType(level) {
  const typeMap = {
    'expert': 'danger',
    'advanced': 'warning',
    'intermediate': 'success',
    'beginner': 'info'
  }
  return typeMap[level] || 'info'
}

function getExpertiseLevelLabel(level) {
  const labelMap = {
    'expert': '专家',
    'advanced': '高级',
    'intermediate': '中级',
    'beginner': '入门'
  }
  return labelMap[level] || level
}

function refreshStats() {
  if (userStore.userId) {
    statsStore.loadStats()
  }
}

// 组件挂载时如果已有用户ID则加载（处理从其他页面切换过来的情况）
onMounted(() => {
  if (userStore.userId) {
    statsStore.loadStats()
  }
})
</script>

<style scoped lang="scss">
.stats-view {
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
}

.stats-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #0f172a;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;
  text-align: center;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-4px);
    border-color: #6366f1;
  }

  :deep(.el-card__body) {
    padding: 32px 24px;
  }

  .el-icon {
    margin-bottom: 16px;
  }

  .stat-value {
    font-size: 36px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 8px;
  }

  .stat-label {
    font-size: 14px;
    color: #94a3b8;
  }
}

.chart-card {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;

  :deep(.el-card__header) {
    border-bottom: 1px solid #334155;
    font-weight: 600;
  }
}

.type-distribution {
  padding: 20px;
}

.type-item {
  margin-bottom: 20px;

  &:last-child {
    margin-bottom: 0;
  }
}

.type-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;

  .type-name {
    color: #f1f5f9;
  }

  .type-count {
    color: #94a3b8;
    font-weight: 600;
  }
}

.type-bar {
  height: 8px;
  background: rgba(51, 65, 85, 0.5);
  border-radius: 4px;
  overflow: hidden;
}

.type-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.stats-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}

.profile-card {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;

  :deep(.el-card__header) {
    border-bottom: 1px solid #334155;
    font-weight: 600;
  }
}

.profile-content {
  padding: 20px;
}

.profile-section {
  margin-bottom: 24px;

  &:last-child {
    margin-bottom: 0;
  }

  h4 {
    color: #94a3b8;
    font-size: 14px;
    margin: 0 0 12px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
}

.topic-tags, .expertise-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-tag, .expertise-tag {
  font-size: 14px;

  .topic-weight {
    margin-left: 4px;
    opacity: 0.8;
    font-size: 12px;
  }

  .expertise-level {
    margin-left: 4px;
    opacity: 0.7;
    font-size: 12px;
  }
}

.interaction-stats {
  display: flex;
  gap: 20px;

  .stat-item {
    display: flex;
    align-items: center;
    gap: 8px;

    .stat-label {
      color: #64748b;
      font-size: 13px;
    }

    .stat-value {
      color: #f1f5f9;
      font-weight: 600;
      font-size: 18px;
    }
  }
}
</style>
