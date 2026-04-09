<template>
  <div class="profile-view">
    <div class="view-header">
      <div class="title">
        <el-icon><UserFilled /></el-icon>
        <span>用户画像</span>
      </div>
    </div>

    <div class="profile-content">
      <!-- 话题偏好 -->
      <el-card class="profile-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><CollectionTag /></el-icon>
            <span>话题偏好</span>
          </div>
        </template>

        <div v-if="topTopics.length > 0" class="tag-cloud">
          <el-tag
            v-for="topic in topTopics"
            :key="topic.topic"
            :type="getWeightType(topic.weight)"
            effect="dark"
            size="large"
          >
            {{ topic.topic }} ({{ (topic.weight * 100).toFixed(0) }}%)
          </el-tag>
        </div>
        <el-empty v-else description="暂无数据，多聊天来了解您的话题偏好" />
      </el-card>

      <!-- 专业领域 -->
      <el-card class="profile-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Trophy /></el-icon>
            <span>专业领域</span>
          </div>
        </template>

        <div v-if="expertiseAreas.length > 0" class="tag-cloud">
          <el-tag
            v-for="area in expertiseAreas"
            :key="area.domain"
            type="success"
            effect="dark"
          >
            {{ area.domain }}
          </el-tag>
        </div>
        <el-empty v-else description="暂无数据" />
      </el-card>

      <!-- 交互偏好 -->
      <el-card class="profile-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Setting /></el-icon>
            <span>交互偏好</span>
          </div>
        </template>

        <div v-if="hasInteractionStyle" class="interaction-list">
          <div class="interaction-item">
            <span class="label">回复长度偏好</span>
            <el-tag :type="getResponseLengthType">{{ responseLengthLabel }}</el-tag>
          </div>
          <div class="interaction-item">
            <span class="label">正式程度偏好</span>
            <el-tag :type="getFormalityType">{{ formalityLabel }}</el-tag>
          </div>
          <div class="interaction-item">
            <span class="label">技术细节偏好</span>
            <el-tag :type="getDetailType">{{ detailLevelLabel }}</el-tag>
          </div>
        </div>
        <el-empty v-else description="暂无数据" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { UserFilled, CollectionTag, Trophy, Setting } from '@element-plus/icons-vue'
import { useStatsStore } from '@/stores/stats'
import { useUserStore } from '@/stores/user'

const statsStore = useStatsStore()
const userStore = useUserStore()

const topTopics = computed(() => statsStore.stats.profile?.top_topics || [])
const expertiseAreas = computed(() => statsStore.stats.profile?.expertise_areas || [])
const interactionStyle = computed(() => statsStore.stats.profile?.interaction_style || {})

const hasInteractionStyle = computed(() => {
  return interactionStyle.value?.preferred_response_length ||
         interactionStyle.value?.preferred_formality ||
         interactionStyle.value?.preferred_detail_level
})

const responseLengthLabel = computed(() => {
  const map = { short: '简洁', long: '详细', medium: '适中' }
  return map[interactionStyle.value?.preferred_response_length] || '适中'
})

const formalityLabel = computed(() => {
  const map = { formal: '正式', casual: '随意', neutral: '适中' }
  return map[interactionStyle.value?.preferred_formality] || '适中'
})

const detailLevelLabel = computed(() => {
  const map = {
    concise: '简洁',
    balanced: '均衡',
    detailed: '详细',
    high: '高',
    low: '低',
    medium: '适中'
  }
  return map[interactionStyle.value?.preferred_detail_level] || '适中'
})

const getResponseLengthType = computed(() => {
  const map = { short: 'info', long: 'warning', medium: '' }
  return map[interactionStyle.value?.preferred_response_length] || ''
})

const getFormalityType = computed(() => {
  const map = { formal: 'success', casual: 'info', neutral: '' }
  return map[interactionStyle.value?.preferred_formality] || ''
})

const getDetailType = computed(() => {
  const map = {
    concise: 'info',
    balanced: '',
    detailed: 'warning',
    high: 'danger',
    low: 'info',
    medium: ''
  }
  return map[interactionStyle.value?.preferred_detail_level] || ''
})

function getWeightType(weight) {
  if (weight > 0.7) return 'danger'
  if (weight > 0.4) return 'warning'
  return 'info'
}

watch(() => userStore.userId, (newUserId) => {
  if (newUserId) {
    statsStore.loadStats()
  }
}, { immediate: true })

onMounted(() => {
  if (userStore.userId) {
    statsStore.loadStats()
  }
})
</script>

<style scoped lang="scss">
.profile-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.view-header {
  padding: 20px 24px;
  border-bottom: 1px solid #334155;
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

.profile-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #0f172a;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 24px;
}

.profile-card {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;

  :deep(.el-card__header) {
    border-bottom: 1px solid #334155;
    padding: 16px 20px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;

  .el-icon {
    color: #6366f1;
  }
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.interaction-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.interaction-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #334155;

  &:last-child {
    border-bottom: none;
  }

  .label {
    color: #94a3b8;
    font-size: 14px;
  }
}
</style>
