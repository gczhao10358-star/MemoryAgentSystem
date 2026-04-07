<template>
  <div class="profile-view">
    <div class="view-header">
      <div class="view-header-copy">
        <div class="title">
          <el-icon><UserFilled /></el-icon>
          <span>用户画像</span>
        </div>
        <div class="subtitle">查看和调整你的交互风格，让助理更贴近你的表达习惯。</div>
      </div>
    </div>

    <div class="profile-content">
      <el-card class="profile-card profile-summary-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><UserFilled /></el-icon>
            <span>基础资料</span>
          </div>
        </template>

        <div class="profile-summary">
          <div class="summary-meta">
            <div class="summary-item">
              <span class="summary-label">用户 ID</span>
              <span class="summary-value mono">{{ userStore.userId || '-' }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">用户名</span>
              <span class="summary-value">{{ userStore.username || '-' }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">累计交互</span>
              <span class="summary-value">{{ currentUser.total_interactions || 0 }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">累计提问</span>
              <span class="summary-value">{{ currentUser.total_queries || 0 }}</span>
            </div>
          </div>

          <el-form label-position="top" class="profile-form">
            <el-form-item label="展示名称">
              <el-input
                v-model="profileForm.name"
                placeholder="给自己起个更自然的名字"
                maxlength="40"
              />
            </el-form-item>

            <div class="style-grid">
              <el-form-item label="回复长度偏好">
                <el-select v-model="profileForm.interaction_style.preferred_response_length">
                  <el-option label="简洁" value="short" />
                  <el-option label="适中" value="medium" />
                  <el-option label="详细" value="long" />
                </el-select>
              </el-form-item>

              <el-form-item label="正式程度偏好">
                <el-select v-model="profileForm.interaction_style.preferred_formality">
                  <el-option label="随意" value="casual" />
                  <el-option label="适中" value="neutral" />
                  <el-option label="正式" value="formal" />
                </el-select>
              </el-form-item>

              <el-form-item label="技术细节偏好">
                <el-select v-model="profileForm.interaction_style.preferred_detail_level">
                  <el-option label="简洁" value="concise" />
                  <el-option label="均衡" value="balanced" />
                  <el-option label="详细" value="detailed" />
                </el-select>
              </el-form-item>

              <el-form-item label="主动性偏好">
                <el-select v-model="profileForm.interaction_style.proactivity_level">
                  <el-option label="被动" value="reactive" />
                  <el-option label="均衡" value="balanced" />
                  <el-option label="主动" value="proactive" />
                </el-select>
              </el-form-item>
            </div>

            <div class="form-actions">
              <el-button
                type="primary"
                :loading="userStore.isLoading"
                @click="saveProfile"
              >
                保存资料
              </el-button>
              <el-button @click="resetProfileForm">重置</el-button>
            </div>
          </el-form>
        </div>
      </el-card>

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

        <div v-if="hasInteractionStyle" class="interaction-grid">
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
          <div class="interaction-item">
            <span class="label">主动性偏好</span>
            <el-tag :type="getProactivityType">{{ proactivityLabel }}</el-tag>
          </div>
        </div>
        <el-empty v-else description="暂无数据" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UserFilled, CollectionTag, Trophy, Setting } from '@element-plus/icons-vue'
import { useStatsStore } from '@/stores/stats'
import { useUserStore } from '@/stores/user'

const statsStore = useStatsStore()
const userStore = useUserStore()
const currentUser = computed(() => userStore.profile || {})

const profileForm = reactive({
  name: '',
  interaction_style: {
    preferred_response_length: 'medium',
    preferred_formality: 'neutral',
    preferred_detail_level: 'balanced',
    proactivity_level: 'balanced'
  }
})

const topTopics = computed(() => statsStore.stats.profile?.top_topics || [])
const expertiseAreas = computed(() => statsStore.stats.profile?.expertise_areas || [])
const interactionStyle = computed(() => {
  return currentUser.value?.interaction_style || statsStore.stats.profile?.interaction_style || {}
})

const hasInteractionStyle = computed(() => {
  return interactionStyle.value?.preferred_response_length ||
         interactionStyle.value?.preferred_formality ||
         interactionStyle.value?.preferred_detail_level ||
         interactionStyle.value?.proactivity_level
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

const proactivityLabel = computed(() => {
  const map = {
    reactive: '被动',
    balanced: '均衡',
    proactive: '主动'
  }
  return map[interactionStyle.value?.proactivity_level] || '均衡'
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

const getProactivityType = computed(() => {
  const map = {
    reactive: 'info',
    balanced: '',
    proactive: 'success'
  }
  return map[interactionStyle.value?.proactivity_level] || ''
})

function getWeightType(weight) {
  if (weight > 0.7) return 'danger'
  if (weight > 0.4) return 'warning'
  return 'info'
}

function resetProfileForm() {
  profileForm.name = currentUser.value?.name || ''
  profileForm.interaction_style.preferred_response_length =
    currentUser.value?.interaction_style?.preferred_response_length || 'medium'
  profileForm.interaction_style.preferred_formality =
    currentUser.value?.interaction_style?.preferred_formality || 'neutral'
  profileForm.interaction_style.preferred_detail_level =
    currentUser.value?.interaction_style?.preferred_detail_level || 'balanced'
  profileForm.interaction_style.proactivity_level =
    currentUser.value?.interaction_style?.proactivity_level || 'balanced'
}

async function saveProfile() {
  const result = await userStore.updateCurrentUser({
    name: profileForm.name,
    interaction_style: {
      ...profileForm.interaction_style
    }
  })

  if (result.success) {
    ElMessage.success('用户资料已更新')
    resetProfileForm()
  } else {
    ElMessage.error(result.error || '保存失败')
  }
}

watch(() => userStore.userId, (newUserId) => {
  if (newUserId) {
    userStore.fetchCurrentUser(newUserId)
    statsStore.loadStats()
  }
}, { immediate: true })

watch(() => userStore.profile, () => {
  resetProfileForm()
}, { immediate: true, deep: true })

onMounted(() => {
  if (userStore.userId) {
    userStore.fetchCurrentUser(userStore.userId)
    statsStore.loadStats()
  }
})
</script>

<style scoped lang="scss">
.profile-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 22%),
    linear-gradient(180deg, #07111f 0%, #0b1324 50%, #0a1423 100%);
}

.view-header {
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

.profile-content {
  flex: 1;
  overflow-y: auto;
  padding: 4px 2px 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 24px;
}

.profile-card {
  background: linear-gradient(180deg, rgba(13, 24, 40, 0.92) 0%, rgba(10, 19, 33, 0.88) 100%);
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 24px;
  box-shadow: 0 18px 36px rgba(2, 6, 23, 0.14);

  :deep(.el-card__header) {
    border-bottom: 1px solid rgba(127, 156, 191, 0.12);
    padding: 16px 20px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #edf7ff;

  .el-icon {
    color: #5eead4;
  }
}

.profile-summary {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.summary-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(127, 156, 191, 0.12);
}

.summary-label {
  color: #8ea3bf;
  font-size: 12px;
}

.summary-value {
  color: #eef6ff;
  font-size: 16px;
  font-weight: 600;
}

.mono {
  font-family: 'SFMono-Regular', Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 13px;
}

.profile-form {
  :deep(.el-form-item__label) {
    color: #cfe0f2;
  }

  :deep(.el-input__wrapper),
  :deep(.el-select__wrapper) {
    background: rgba(15, 23, 42, 0.72);
    box-shadow: none;
    border: 1px solid rgba(127, 156, 191, 0.14);
  }
}

.style-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.interaction-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.interaction-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-height: 92px;
  padding: 14px;
  border: 1px solid rgba(127, 156, 191, 0.12);
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.62);

  .label {
    color: #8ea3bf;
    font-size: 13px;
  }
}

@media (max-width: 960px) {
  .profile-view {
    padding: 12px;
    gap: 12px;
  }

  .profile-content {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .interaction-grid {
    grid-template-columns: 1fr;
  }
}
</style>
