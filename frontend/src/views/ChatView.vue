<template>
  <div class="chat-view">
    <transition name="session-backdrop-fade">
      <button
        v-if="showSessionPanel"
        type="button"
        class="session-backdrop"
        aria-label="关闭会话面板"
        @click="showSessionPanel = false"
      ></button>
    </transition>

    <aside :class="['session-sidebar', { open: showSessionPanel }]">
      <div class="session-sidebar-header">
        <div class="session-header-copy">
          <div class="session-title">会话列表</div>
          <div class="session-subtitle">按对话线程管理上下文</div>
        </div>
        <div class="session-header-actions">
          <el-button type="primary" class="session-new-button" @click="handleNewSession">
            <el-icon><Plus /></el-icon>
            新建对话
          </el-button>
          <el-button text circle class="session-close-button" @click="showSessionPanel = false">
            <el-icon><CloseBold /></el-icon>
          </el-button>
        </div>
      </div>

      <div class="session-search">
        <el-input
          v-model="sessionSearchQuery"
          placeholder="搜索会话标题或内容"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <div v-if="chatStore.sessionsLoading" class="session-loading">
        正在加载会话...
      </div>

      <div
        v-else-if="filteredActiveSessions.length === 0 && filteredArchivedSessions.length === 0"
        class="session-empty"
      >
        <div class="session-empty-title">还没有历史会话</div>
        <div class="session-empty-text">创建一个新会话后，这里会保存聊天线程。</div>
      </div>

      <div v-else class="session-sections">
        <div class="session-overview">
          <div
            v-for="item in sessionInsights"
            :key="item.label"
            class="session-overview-card"
          >
            <div class="session-overview-label">{{ item.label }}</div>
            <div class="session-overview-value">{{ item.value }}</div>
          </div>
        </div>

        <div class="session-section">
          <div class="session-section-header">
            <span>当前会话</span>
            <span class="session-section-count">{{ filteredActiveSessions.length }}</span>
          </div>

          <div v-if="filteredActiveSessions.length === 0" class="session-section-empty">
            当前没有活跃会话
          </div>

          <div v-else class="session-list">
            <div
              v-for="session in filteredActiveSessions"
              :key="session.session_id"
              :class="['session-item', { active: session.session_id === chatStore.currentSessionId }]"
            >
              <button
                type="button"
                class="session-item-body"
                @click="handleSessionSwitch(session.session_id)"
              >
                <div class="session-item-heading">
                  <div class="session-item-title">{{ formatSessionTitle(session) }}</div>
                  <div class="session-item-heading-badges">
                    <span v-if="isSessionPinned(session.session_id)" class="session-item-badge muted icon-badge">
                      <el-icon><Top /></el-icon>
                      置顶
                    </span>
                    <span
                      v-if="session.session_id === chatStore.currentSessionId"
                      class="session-item-badge"
                    >
                      当前
                    </span>
                  </div>
                </div>
                <div class="session-item-preview">{{ formatSessionPreview(session) }}</div>
                <div class="session-item-meta">
                  <span>{{ session.message_count || 0 }} 条消息</span>
                  <span>{{ formatSessionTime(session.last_message_at || session.updated_at || session.created_at) }}</span>
                </div>
              </button>
              <div class="session-item-actions">
                <el-button text size="small" @click.stop="toggleSessionPinned(session.session_id)">
                  {{ isSessionPinned(session.session_id) ? '取消置顶' : '置顶' }}
                </el-button>
                <el-button text size="small" @click.stop="handleRenameSession(session)">
                  重命名
                </el-button>
                <el-button text size="small" @click.stop="handleArchiveSession(session)">
                  归档
                </el-button>
                <el-button text size="small" type="danger" @click.stop="handleDeleteSession(session)">
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="session-section archived">
          <button type="button" class="session-section-header toggle" @click="showArchived = !showArchived">
            <span>已归档</span>
            <div class="session-section-header-right">
              <span class="session-section-count">{{ filteredArchivedSessions.length }}</span>
              <el-icon :class="['toggle-icon', { expanded: showArchived }]"><ArrowDown /></el-icon>
            </div>
          </button>

          <div v-if="showArchived && filteredArchivedSessions.length === 0" class="session-section-empty">
            暂无已归档会话
          </div>

          <div v-else-if="showArchived" class="session-list archived-list">
            <div
              v-for="session in filteredArchivedSessions"
              :key="session.session_id"
              class="session-item archived-item"
            >
              <div class="session-item-body archived-body">
                <div class="session-item-heading">
                  <div class="session-item-title">{{ formatSessionTitle(session) }}</div>
                  <div class="session-item-heading-badges">
                    <span v-if="isSessionPinned(session.session_id)" class="session-item-badge muted icon-badge">
                      <el-icon><Top /></el-icon>
                      置顶
                    </span>
                    <span class="session-item-badge muted">归档</span>
                  </div>
                </div>
                <div class="session-item-preview">{{ formatSessionPreview(session) }}</div>
                <div class="session-item-meta">
                  <span>{{ session.message_count || 0 }} 条消息</span>
                  <span>{{ formatSessionTime(session.last_message_at || session.updated_at || session.created_at) }}</span>
                </div>
              </div>
              <div class="session-item-actions">
                <el-button text size="small" @click.stop="toggleSessionPinned(session.session_id)">
                  {{ isSessionPinned(session.session_id) ? '取消置顶' : '置顶' }}
                </el-button>
                <el-button text size="small" type="primary" @click.stop="handleRestoreSession(session)">
                  恢复
                </el-button>
                <el-button text size="small" type="danger" @click.stop="handleDeleteSession(session)">
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <div class="chat-panel">
      <div class="chat-header">
        <div class="chat-header-main">
          <button
            type="button"
            class="session-toggle"
            aria-label="打开会话面板"
            @click="showSessionPanel = !showSessionPanel"
          >
            <el-icon><Operation /></el-icon>
          </button>
          <div class="chat-heading">
            <div class="chat-heading-top">
              <div class="title">
                <el-icon><ChatRound /></el-icon>
                <span>智忆助理</span>
              </div>
              <span class="chat-pill">当前线程</span>
            </div>
            <div class="chat-session-title">{{ formatSessionTitle(currentSession) }}</div>
            <div class="chat-session-meta">
              {{ chatStore.activeSessions.length }} 个活跃会话 · {{ currentSession?.message_count || chatStore.messages.length }} 条消息 · 最后活跃 {{ currentSessionActivityLabel }}
            </div>
          </div>
        </div>
        <div class="status">
          <span class="status-dot"></span>
          <span>在线</span>
        </div>
      </div>

      <div :class="['chat-messages', { empty: chatStore.messages.length === 0 }]" ref="messagesRef">
        <div :class="['chat-messages-track', { empty: chatStore.messages.length === 0 }]">
          <div v-if="chatStore.messages.length === 0" class="welcome-message">
            <div class="welcome-badge">Memory workspace</div>
            <h3>欢迎使用智忆助理</h3>
            <p>把聊天、会话历史和长期记忆放在一个更顺手的工作台里。</p>
            <div class="welcome-grid">
              <div class="welcome-card">
                <div class="welcome-card-title">快速开始</div>
                <div class="welcome-card-subtitle">选一个入口，马上开始一段更有上下文的对话。</div>
                <div class="starter-list">
                  <button
                    v-for="(item, index) in quickActions"
                    :key="index"
                    type="button"
                    class="starter-item"
                    @click="sendQuickMessage(item.text)"
                  >
                    <div class="starter-item-title">{{ item.title }}</div>
                    <div class="starter-item-text">{{ item.text }}</div>
                  </button>
                </div>
              </div>
              <div class="welcome-card">
                <div class="welcome-card-title">这个工作台能做什么</div>
                <div class="welcome-capabilities">
                  <div
                    v-for="item in capabilityHighlights"
                    :key="item.title"
                    class="capability-item"
                  >
                    <div class="capability-title">{{ item.title }}</div>
                    <div class="capability-text">{{ item.text }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div
            v-for="message in chatStore.messages"
            :key="message.id"
            :class="['message', message.role, { error: message.error }]"
          >
            <el-avatar :size="38" :class="message.role">
              <el-icon v-if="message.role === 'user'"><UserFilled /></el-icon>
              <el-icon v-else><Cpu /></el-icon>
            </el-avatar>
            <div class="message-content">
              <div class="message-text" v-html="formatMessage(message.content)"></div>
              <div v-if="isAnalysisMessage(message.content)" class="analysis-actions">
                <el-button type="primary" size="small" @click="showAnalysisResult">
                  <el-icon><Document /></el-icon>
                  查看分析详情
                </el-button>
              </div>
              <div class="message-time">{{ message.time }}</div>
            </div>
          </div>

          <div v-if="chatStore.isTyping" class="message assistant typing">
            <el-avatar :size="38" class="assistant">
              <el-icon><Cpu /></el-icon>
            </el-avatar>
            <div class="message-content">
              <el-icon class="typing-icon"><Loading /></el-icon>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-shell">
        <div class="chat-input-area">
          <div class="input-toolbar">
            <el-button type="info" text @click="showRememberDialog = true">
              <el-icon><Collection /></el-icon>
              添加记忆
            </el-button>
            <el-button type="info" text @click="showSearchDialog = true">
              <el-icon><Search /></el-icon>
              搜索记忆
            </el-button>
            <el-button type="info" text @click="openUploadDialog">
              <el-icon><Upload /></el-icon>
              上传会议记录
            </el-button>
          </div>
          <div class="input-group">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="1"
              placeholder="输入消息..."
              resize="none"
              @keydown="handleInputKeydown"
            />
            <el-button
              type="primary"
              :disabled="!inputMessage.trim() || chatStore.isTyping"
              @click="handleSend"
            >
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
          <div class="input-footer">
            <span>Enter 发送，Shift + Enter 换行</span>
            <span>当前会话会自动保存上下文</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加记忆对话框 -->
    <el-dialog v-model="showRememberDialog" title="添加记忆" width="500px">
      <el-form :model="rememberForm" label-position="top">
        <el-form-item label="记忆内容">
          <el-input
            v-model="rememberForm.content"
            type="textarea"
            :rows="4"
            placeholder="输入要记忆的内容..."
          />
        </el-form-item>
        <el-form-item label="记忆类型">
          <el-select v-model="rememberForm.type" style="width: 100%">
            <el-option label="事实" value="fact" />
            <el-option label="事件" value="event" />
            <el-option label="任务" value="task" />
            <el-option label="提醒" value="reminder" />
            <el-option label="文档" value="document" />
          </el-select>
        </el-form-item>
        <el-form-item label="重要性">
          <el-slider v-model="rememberForm.importance" :min="0" :max="1" :step="0.1" show-stops />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRememberDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRemember" :loading="rememberLoading">保存</el-button>
      </template>
    </el-dialog>

    <!-- 搜索记忆对话框 -->
    <el-dialog v-model="showSearchDialog" title="搜索记忆" width="600px">
      <el-input
        v-model="searchQuery"
        placeholder="输入关键词搜索..."
        @keyup.enter="handleSearch"
      >
        <template #append>
          <el-button @click="handleSearch">
            <el-icon><Search /></el-icon>
          </el-button>
        </template>
      </el-input>
      <div class="search-results" v-if="memoryStore.searchResults.length > 0">
        <el-card
          v-for="item in memoryStore.searchResults"
          :key="item.memory_id"
          class="search-result-item"
          shadow="hover"
        >
          <div class="result-score">
            <el-icon><StarFilled /></el-icon>
            相关度: {{ (item.score * 100).toFixed(1) }}%
          </div>
          <div class="result-content">{{ item.content }}</div>
        </el-card>
      </div>
      <el-empty v-else-if="searched" description="未找到相关记忆" />
      <template #footer>
        <el-button @click="showSearchDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 上传会议记录对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传会议记录"
      width="600px"
      :close-on-click-modal="false"
      :show-close="!isUploading"
      @close="handleDialogClose"
    >
      <!-- 步骤1: 上传区域 (没有结果且没有在处理时显示) -->
      <div v-if="!uploadResult && !isProcessing" class="upload-area">
        <el-upload
          ref="uploadRef"
          class="document-uploader"
          drag
          action="/api/documents/upload"
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          accept=".pdf,.docx,.txt,.md"
        >
          <el-icon class="el-icon--upload"><Upload /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 PDF, DOCX, TXT, Markdown 格式，文件大小不超过 10MB
            </div>
          </template>
        </el-upload>

        <!-- 已选文件显示 -->
        <div v-if="selectedFile && !isUploading" class="selected-file-info">
          <el-alert type="success" :closable="false">
            <template #title>
              已选择文件：{{ selectedFile.name }}
            </template>
            大小：{{ (selectedFile.size / 1024).toFixed(2) }} KB
          </el-alert>
        </div>

        <!-- 上传进度 -->
        <div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress">
          <el-progress :percentage="uploadProgress" :stroke-width="8" />
        </div>
      </div>

      <!-- 步骤2: 处理进度显示 (正在处理时显示) -->
      <div v-else-if="isProcessing" class="processing-area">
        <div class="processing-header">
          <el-icon class="processing-icon" :size="48" color="#6366f1"><Loading /></el-icon>
          <h4>正在解析会议记录...</h4>
          <p class="processing-stage">{{ processingStage }}</p>
          <p class="processing-hint">请稍候，正在使用AI分析文档内容</p>
        </div>
        <el-progress
          :percentage="processingProgress"
          :stroke-width="12"
          :status="processingProgress >= 100 ? 'success' : ''"
        />
        <div class="processing-details">
          <el-tag v-if="processingChunkCount > 0" type="info" size="large">
            已分析 {{ processingChunkCount }} 个片段
          </el-tag>
          <el-tag v-else type="warning" size="large">初始化中...</el-tag>
        </div>
      </div>

      <!-- 解析结果展示 -->
      <div v-else-if="uploadResult" class="result-area">
        <div class="result-header">
          <el-icon :size="32" color="#10b981"><CircleCheck /></el-icon>
          <h4>解析完成</h4>
        </div>

        <div class="result-content">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="会议主题">
              {{ uploadResult.meeting_title || '未识别' }}
            </el-descriptions-item>
            <el-descriptions-item label="会议日期">
              {{ uploadResult.meeting_date || '未识别' }}
            </el-descriptions-item>
            <el-descriptions-item label="参会人员">
              {{ uploadResult.participants?.join(', ') || '未识别' }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="result-section">
            <h5>摘要</h5>
            <p class="summary-text">{{ uploadResult.summary }}</p>
          </div>

          <div v-if="uploadResult.key_decisions?.length > 0" class="result-section">
            <h5>关键决策 ({{ uploadResult.key_decisions.length }})</h5>
            <ul class="decision-list">
              <li v-for="(decision, idx) in uploadResult.key_decisions" :key="idx">
                {{ decision }}
              </li>
            </ul>
          </div>

          <div v-if="uploadResult.action_items?.length > 0" class="result-section">
            <h5>待办事项 ({{ uploadResult.action_items.length }})</h5>
            <el-checkbox-group v-model="selectedActionItems">
              <div
                v-for="(item, idx) in uploadResult.action_items"
                :key="idx"
                class="action-item"
              >
                <el-checkbox :label="idx">
                  <div class="action-item-content">
                    <span class="action-text">{{ item.content }}</span>
                    <span v-if="item.assignee" class="action-assignee">@{{ item.assignee }}</span>
                  </div>
                </el-checkbox>
                <el-date-picker
                  v-if="selectedActionItems.includes(idx)"
                  v-model="actionItemDates[idx]"
                  type="datetime"
                  placeholder="选择提醒时间"
                  size="small"
                  style="margin-left: 24px; margin-top: 8px;"
                />
              </div>
            </el-checkbox-group>
          </div>
        </div>
      </div>

      <template #footer>
        <!-- 上传阶段 -->
        <div v-if="!uploadResult && !isProcessing">
          <el-button @click="showUploadDialog = false" :disabled="isUploading">取消</el-button>
          <el-button
            type="primary"
            @click="handleUpload"
            :loading="isUploading"
            :disabled="!selectedFile || isUploading"
          >
            {{ isUploading ? '上传中...' : '开始解析' }}
          </el-button>
        </div>

        <!-- 解析阶段 - 不显示按钮，只显示关闭 -->
        <div v-else-if="isProcessing">
          <el-button @click="showUploadDialog = false" disabled>解析中...</el-button>
        </div>

        <!-- 结果展示阶段 -->
        <div v-else-if="uploadResult">
          <el-button @click="resetUpload">上传新文件</el-button>
          <el-button
            v-if="selectedActionItems.length > 0"
            type="primary"
            @click="confirmActionItems"
            :loading="isConfirming"
          >
            创建 {{ selectedActionItems.length }} 个提醒
          </el-button>
          <el-button v-else type="primary" @click="showUploadDialog = false">完成</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import {
  ChatRound, Cpu, UserFilled, Loading,
  Collection, Search, Promotion, StarFilled,
  Upload, Document, CircleCheck, Warning, ArrowDown,
  Operation, CloseBold, Plus, Top
} from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { useMemoryStore } from '@/stores/memory'
import { useUserStore } from '@/stores/user'

const chatStore = useChatStore()
const memoryStore = useMemoryStore()
const userStore = useUserStore()

const messagesRef = ref(null)
const inputMessage = ref('')
const showRememberDialog = ref(false)
const showSearchDialog = ref(false)
const showUploadDialog = ref(false)
const searchQuery = ref('')
const searched = ref(false)
const rememberLoading = ref(false)
const showArchived = ref(false)
const showSessionPanel = ref(false)
const sessionSearchQuery = ref('')

// 文件上传相关
const uploadRef = ref(null)
const selectedFile = ref(null)
const isUploading = ref(false)
const isProcessing = ref(false)
const uploadProgress = ref(0)
const processingProgress = ref(0)
const processingStage = ref('准备中...')
const processingChunkCount = ref(0)
const uploadResult = ref(null)
const selectedActionItems = ref([])
const actionItemDates = ref({})
const isConfirming = ref(false)
const uploadTargetSessionId = ref('')

// 从 localStorage 恢复最后一次分析结果
const savedResult = localStorage.getItem('last_analysis_result')
if (savedResult) {
  try {
    uploadResult.value = JSON.parse(savedResult)
  } catch (e) {
    console.error('解析保存的分析结果失败:', e)
  }
}

// 监听 uploadResult 变化并保存到 localStorage
watch(uploadResult, (newVal) => {
  if (newVal) {
    localStorage.setItem('last_analysis_result', JSON.stringify(newVal))
  } else {
    localStorage.removeItem('last_analysis_result')
  }
}, { deep: true })

const quickActions = [
  {
    title: '认识一下助理',
    text: '你好，请介绍一下你自己'
  },
  {
    title: '看看它能记什么',
    text: '你能记住什么信息？'
  },
  {
    title: '马上存一条记忆',
    text: '帮我记录一个重要的事情'
  }
]

const capabilityHighlights = [
  {
    title: '持续记住上下文',
    text: '同一会话会自动延续历史，不用反复补背景。'
  },
  {
    title: '随手沉淀长期记忆',
    text: '重要信息可直接存成记忆，后续检索更稳。'
  },
  {
    title: '整理会议与待办',
    text: '上传会议记录后，可提取摘要、决策和待办。'
  }
]

const currentSession = computed(() => {
  return chatStore.sessions.find((session) => session.session_id === chatStore.currentSessionId) || null
})

function getPinnedSessionStorageKey() {
  return userStore.userId ? `memorymate_pinned_sessions_${userStore.userId}` : ''
}

function loadPinnedSessionIds() {
  const storageKey = getPinnedSessionStorageKey()
  if (!storageKey) return []

  try {
    const rawValue = localStorage.getItem(storageKey)
    const parsed = rawValue ? JSON.parse(rawValue) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const pinnedSessionIds = ref(loadPinnedSessionIds())

const totalMessageCount = computed(() => {
  return chatStore.sessions.reduce((total, session) => total + (session.message_count || 0), 0)
})

const sessionInsights = computed(() => {
  return [
    { label: '活跃会话', value: chatStore.activeSessions.length },
    { label: '已归档', value: chatStore.archivedSessions.length },
    { label: '总消息', value: totalMessageCount.value }
  ]
})

const currentSessionActivityLabel = computed(() => {
  const value = currentSession.value?.last_message_at || currentSession.value?.updated_at || currentSession.value?.created_at
  return value ? formatSessionTime(value) : '刚刚'
})

const normalizedSessionQuery = computed(() => sessionSearchQuery.value.trim().toLowerCase())

function isSessionPinned(sessionId) {
  return pinnedSessionIds.value.includes(sessionId)
}

function persistPinnedSessions() {
  const storageKey = getPinnedSessionStorageKey()
  if (!storageKey) return
  localStorage.setItem(storageKey, JSON.stringify(pinnedSessionIds.value))
}

function getSessionMessageCount(session) {
  return Number(session?.message_count || 0)
}

function getSessionActivityTime(session) {
  const value = session?.last_message_at || session?.updated_at || session?.created_at || 0
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? 0 : timestamp
}

function sortSessions(sessions) {
  return [...sessions].sort((left, right) => {
    const leftPinned = isSessionPinned(left.session_id) ? 1 : 0
    const rightPinned = isSessionPinned(right.session_id) ? 1 : 0

    if (leftPinned !== rightPinned) {
      return rightPinned - leftPinned
    }

    const leftHasMessages = getSessionMessageCount(left) > 0 ? 1 : 0
    const rightHasMessages = getSessionMessageCount(right) > 0 ? 1 : 0

    if (leftHasMessages !== rightHasMessages) {
      return rightHasMessages - leftHasMessages
    }

    const leftTime = getSessionActivityTime(left)
    const rightTime = getSessionActivityTime(right)
    return rightTime - leftTime
  })
}

function filterSessions(sessions) {
  if (!normalizedSessionQuery.value) {
    return sortSessions(sessions)
  }

  const query = normalizedSessionQuery.value
  return sortSessions(
    sessions.filter((session) => {
      const title = formatSessionTitle(session).toLowerCase()
      const preview = formatSessionPreview(session).toLowerCase()
      return title.includes(query) || preview.includes(query)
    })
  )
}

const filteredActiveSessions = computed(() => filterSessions(chatStore.activeSessions))
const filteredArchivedSessions = computed(() => filterSessions(chatStore.archivedSessions))

const rememberForm = ref({
  content: '',
  type: 'fact',
  importance: 0.5
})

function normalizeMessageContent(content) {
  if (typeof content !== 'string') {
    return ''
  }

  return content
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
}

function formatMessage(content) {
  return marked(normalizeMessageContent(content), { breaks: true })
}

function formatSessionTitle(session) {
  return session?.title || session?.preview || '新对话'
}

function formatSessionPreview(session) {
  return session?.preview || session?.summary || '暂无消息内容'
}

function formatSessionTime(value) {
  if (!value) return '刚刚'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'

  const now = new Date()
  const sameDay = now.toDateString() === date.toDateString()
  if (sameDay) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return date.toLocaleDateString([], { month: 'numeric', day: 'numeric' })
}

// 重新查看分析结果
function showAnalysisResult() {
  if (uploadResult.value) {
    showUploadDialog.value = true
  } else {
    ElMessage.warning('没有找到分析结果，请重新上传文档')
  }
}

// 检查消息是否包含会议解析内容
function isAnalysisMessage(content) {
  return content && content.includes('会议记录解析完成')
}

async function handleSend() {
  if (!inputMessage.value.trim() || chatStore.isTyping) return
  const message = inputMessage.value
  inputMessage.value = ''
  await chatStore.sendMessage(message)
}

function handleInputKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey) {
    return
  }
  event.preventDefault()
  handleSend()
}

function toggleSessionPinned(sessionId) {
  if (!sessionId) return

  if (isSessionPinned(sessionId)) {
    pinnedSessionIds.value = pinnedSessionIds.value.filter((item) => item !== sessionId)
  } else {
    pinnedSessionIds.value = [sessionId, ...pinnedSessionIds.value]
  }
  persistPinnedSessions()
}

function sendQuickMessage(text) {
  inputMessage.value = text
  handleSend()
}

async function handleNewSession() {
  try {
    await chatStore.startNewSession()
    showSessionPanel.value = false
  } catch (error) {
    ElMessage.error(error.message || '创建会话失败')
  }
}

async function handleSessionSwitch(sessionId) {
  if (!sessionId || sessionId === chatStore.currentSessionId) return

  try {
    await chatStore.switchSession(sessionId)
    showSessionPanel.value = false
  } catch (error) {
    ElMessage.error(error.message || '切换会话失败')
  }
}

async function handleRenameSession(session) {
  try {
    const { value } = await ElMessageBox.prompt('输入新的会话标题', '重命名会话', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: formatSessionTitle(session),
      inputValidator: (inputValue) => {
        if (!inputValue || !inputValue.trim()) {
          return '标题不能为空'
        }
        return true
      }
    })

    await chatStore.renameSession(session.session_id, value)
    ElMessage.success('会话已重命名')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error.message || '重命名失败')
  }
}

async function handleArchiveSession(session) {
  try {
    await ElMessageBox.confirm(
      `确认归档会话“${formatSessionTitle(session)}”吗？归档后它会从默认列表中隐藏。`,
      '归档会话',
      {
        confirmButtonText: '归档',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await chatStore.archiveSession(session.session_id)
    ElMessage.success('会话已归档')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error.message || '归档失败')
  }
}

async function handleRestoreSession(session) {
  try {
    await chatStore.restoreSession(session.session_id)
    showSessionPanel.value = false
    ElMessage.success('会话已恢复到当前列表')
  } catch (error) {
    ElMessage.error(error.message || '恢复失败')
  }
}

async function handleDeleteSession(session) {
  try {
    await ElMessageBox.confirm(
      `确认删除会话“${formatSessionTitle(session)}”吗？该会话的历史消息会一起删除。`,
      '删除会话',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await chatStore.deleteSession(session.session_id)
    ElMessage.success('会话已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error.message || '删除失败')
  }
}

async function handleRemember() {
  if (!rememberForm.value.content.trim()) {
    ElMessage.warning('请输入记忆内容')
    return
  }

  rememberLoading.value = true
  const result = await memoryStore.addMemory(
    rememberForm.value.content,
    rememberForm.value.type,
    rememberForm.value.importance
  )
  rememberLoading.value = false

  if (result.success) {
    ElMessage.success('记忆已保存')
    showRememberDialog.value = false
    rememberForm.value = { content: '', type: 'fact', importance: 0.5 }
  } else {
    ElMessage.error(result.error || '保存失败')
  }
}

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  searched.value = true
  await memoryStore.searchMemories(searchQuery.value)
}

// 自动滚动到底部
watch(() => chatStore.messages.length, async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
})

watch(() => userStore.userId, () => {
  pinnedSessionIds.value = loadPinnedSessionIds()
  sessionSearchQuery.value = ''
}, { immediate: true })

watch(() => userStore.userId, async (userId) => {
  if (!userId) {
    return
  }
  await chatStore.ensureActiveSession()
}, { immediate: true })

// 文件上传相关方法
function handleFileChange(file, fileList) {
  console.log('=== File Change Event ===')
  console.log('file:', file)
  console.log('file.raw:', file?.raw)
  console.log('file.name:', file?.name)
  console.log('fileList:', fileList)
  console.log('fileList.length:', fileList?.length)

  // 优先使用 file.raw，如果没有则从 fileList 获取
  if (file && file.raw) {
    selectedFile.value = file
    console.log('Selected file from file.raw:', file.name)
  } else if (file && file.name) {
    // 有些情况下 file 本身就是 raw 对象
    selectedFile.value = file
    console.log('Selected file from file:', file.name)
  } else if (fileList && fileList.length > 0) {
    const lastFile = fileList[fileList.length - 1]
    selectedFile.value = lastFile
    console.log('Selected file from fileList:', lastFile.name)
  }

  console.log('Final selectedFile:', selectedFile.value)
  console.log('=== End File Change ===')
}

function handleFileRemove(file, fileList) {
  console.log('=== File Remove Event ===')
  console.log('file:', file)
  console.log('fileList:', fileList)

  if (!fileList || fileList.length === 0) {
    selectedFile.value = null
    console.log('All files removed')
  } else {
    selectedFile.value = fileList[fileList.length - 1]
    console.log('Remaining file:', selectedFile.value?.name)
  }
  console.log('=== End File Remove ===')
}

function openUploadDialog() {
  // 打开对话框前重置状态，确保显示上传界面而非旧结果
  resetUpload()
  uploadTargetSessionId.value = chatStore.currentSessionId || ''
  showUploadDialog.value = true
}

function resetUpload() {
  selectedFile.value = null
  uploadResult.value = null
  uploadTargetSessionId.value = ''
  selectedActionItems.value = []
  actionItemDates.value = {}
  isProcessing.value = false
  isUploading.value = false
  uploadProgress.value = 0
  processingProgress.value = 0
  processingStage.value = '准备中...'
  processingChunkCount.value = 0
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  // 清除 localStorage 中保存的结果
  localStorage.removeItem('last_analysis_result')
}

// 关闭弹窗时保留分析结果，只重置上传状态
function handleDialogClose() {
  selectedFile.value = null
  selectedActionItems.value = []
  actionItemDates.value = {}
  uploadTargetSessionId.value = uploadTargetSessionId.value || chatStore.currentSessionId || ''
  processingProgress.value = 0
  processingStage.value = '准备中...'
  processingChunkCount.value = 0
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  // 注意：不清空 uploadResult，保留分析结果以便重新查看
}

async function handleUpload() {
  console.log('=== handleUpload called ===')
  console.log('selectedFile:', selectedFile.value)

  if (!selectedFile.value) {
    console.error('No file selected')
    ElMessage.warning('请先选择文件')
    return
  }

  // 检查文件对象是否有效
  const hasRaw = selectedFile.value.raw !== undefined
  const hasName = selectedFile.value.name !== undefined
  console.log('File has raw:', hasRaw)
  console.log('File has name:', hasName)

  if (!hasName) {
    console.error('Invalid file object')
    ElMessage.error('文件对象无效，请重新选择文件')
    selectedFile.value = null
    if (uploadRef.value) {
      uploadRef.value.clearFiles()
    }
    return
  }

  // 检查用户是否登录
  if (!userStore.userId) {
    ElMessage.error('请先登录后再上传文件')
    return
  }

  if (!uploadTargetSessionId.value) {
    uploadTargetSessionId.value = chatStore.currentSessionId || ''
  }

  isUploading.value = true
  uploadProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value.raw)
    formData.append('user_id', userStore.userId)
    formData.append('source', 'web')
    if (uploadTargetSessionId.value) {
      formData.append('session_id', uploadTargetSessionId.value)
    }

    console.log('Uploading file:', selectedFile.value.name)

    // 上传文件
    const response = await fetch('/api/documents/upload', {
      method: 'POST',
      body: formData
    })

    const result = await response.json()
    console.log('Upload response:', result)

    if (!result.success) {
      throw new Error(result.error || '上传失败')
    }

    uploadProgress.value = 100
    isUploading.value = false
    isProcessing.value = true
    processingStage.value = '正在连接服务器...'
    processingProgress.value = 5  // 初始进度，让用户知道已经开始

    // 强制等待DOM更新
    await nextTick()
    console.log('State updated - isProcessing:', isProcessing.value)

    // 检查是否是重复文件
    if (result.is_duplicate) {
      console.log('File is duplicate, connecting to get existing result:', result.document_id)
      ElMessage.info(result.message || '该文件已上传过，正在获取解析结果...')
    } else {
      console.log('Starting WebSocket connection for document:', result.document_id)
    }

    // 连接 WebSocket 获取处理进度（新文件或已存在文件都走WebSocket）
    connectProcessingWebSocket(result.document_id, uploadTargetSessionId.value)

  } catch (error) {
    console.error('Upload error:', error)
    ElMessage.error(error.message || '上传失败')
    isUploading.value = false
  }
}

function connectProcessingWebSocket(documentId, sessionId = '') {
  // 使用固定地址而不是 window.location.host 避免一些问题
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = '127.0.0.1:8000'  // 直接使用后端地址
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
  const wsUrl = `${protocol}//${host}/ws/documents/${documentId}${query}`
  console.log('Connecting to WebSocket:', wsUrl)

  const ws = new WebSocket(wsUrl)
  let connectionTimeout = null

  // 设置连接超时
  connectionTimeout = setTimeout(() => {
    console.error('WebSocket connection timeout')
    ElMessage.error('连接超时，请重试')
    isProcessing.value = false
    ws.close()
  }, 10000) // 10秒超时

  ws.onopen = () => {
    console.log('WebSocket connected')
    clearTimeout(connectionTimeout)
    processingStage.value = '已连接，等待数据...'
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.stage === 'heartbeat') {
      return
    }

    // 调试日志
    console.log('=== WebSocket Message ===')
    console.log('Stage:', data.stage)
    console.log('Progress:', data.progress)
    console.log('Full data:', data)

    // 更新进度 - 确保是0-100的数字
    const rawProgress = data.progress || 0
    const percentProgress = Math.round(rawProgress * 100)
    processingProgress.value = percentProgress
    console.log('Set processingProgress to:', percentProgress)

    // 更新处理阶段文本
    const stageMap = {
      'loading': '正在读取文档...',
      'chunking': '正在分析文档结构...',
      'global_analysis': '正在分析会议整体信息...',
      'chunk_analysis': '正在提取详细信息...',
      'consolidation': '正在整合分析结果...',
      'storing': '正在保存记忆...',
      'completed': '处理完成',
      'error': '处理出错'
    }
    processingStage.value = stageMap[data.stage] || data.stage

    if (data.data?.chunk_count) {
      processingChunkCount.value = data.data.chunk_count
    }

    if (data.stage === 'completed') {
      console.log('=== Processing Completed ===')
      console.log('Event data:', data)

      // 先设置结果，再关闭处理状态，避免界面闪烁
      const result = data.data?.result
      const docId = data.data?.document_id

      console.log('Result:', result)
      console.log('Document ID:', docId)

      if (result) {
        // 保存完整的响应数据
        uploadResult.value = {
          ...result,
          document_id: docId
        }
        console.log('uploadResult set to:', uploadResult.value)

        // 关闭处理状态（在设置结果之后）
        isProcessing.value = false

        ElMessage.success('会议记录解析完成！')
        if (uploadTargetSessionId.value) {
          chatStore.fetchSessions().catch((error) => {
            console.error('同步会话列表失败:', error)
          })
          chatStore.loadSessionMessages(uploadTargetSessionId.value).catch((error) => {
            console.error('同步会议解析消息失败:', error)
          })
        }
      } else {
        console.error('No result in completed event')
        ElMessage.error('解析结果为空')
        isProcessing.value = false
      }

      ws.close()
    } else if (data.stage === 'error') {
      isProcessing.value = false
      ElMessage.error(data.data?.error || '处理失败')
      ws.close()
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    clearTimeout(connectionTimeout)
    // 不立即显示错误，让 onclose 处理
  }

  ws.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason)
    clearTimeout(connectionTimeout)
    // 如果还在处理中且不是正常关闭，显示错误
    if (isProcessing.value && event.code !== 1000) {
      console.error('WebSocket closed unexpectedly')
      ElMessage.error('连接已断开，请重试')
      isProcessing.value = false
    }
  }
}

async function confirmActionItems() {
  if (selectedActionItems.value.length === 0) return

  // 检查必要数据 - 必须使用实际登录的用户ID
  const userId = userStore.userId
  const documentId = uploadResult.value?.document_id

  console.log('userId:', userId)
  console.log('documentId:', documentId)
  console.log('uploadResult:', uploadResult.value)

  // 必须先登录
  if (!userId) {
    ElMessage.error('请先登录后再创建待办事项')
    return
  }

  if (!documentId) {
    ElMessage.error('文档ID丢失，请重新上传')
    return
  }

  // 先检查用户是否配置了飞书
  try {
    const statusRes = await fetch(`/api/platform/lark/status?user_id=${userId}`)
    const statusData = await statusRes.json()
    console.log('飞书配置状态:', statusData)

    if (statusData.success && !statusData.data?.configured) {
      // 未配置飞书，提示用户
      ElMessageBox.confirm(
        '您尚未配置飞书通知，创建的任务到期后将无法收到飞书提醒。是否继续？',
        '提示',
        {
          confirmButtonText: '继续创建',
          cancelButtonText: '去配置飞书',
          type: 'warning'
        }
      ).then(() => {
        // 用户选择继续，执行创建
        doConfirmActionItems(userId, documentId)
      }).catch(() => {
        // 用户选择取消，可以跳转到设置页面或显示配置说明
        ElMessage.info('请前往"平台集成"设置页面配置飞书应用')
      })
      return
    }
  } catch (e) {
    console.error('检查飞书配置失败:', e)
    // 继续执行，让后端处理
  }

  // 已配置飞书或检查失败，直接执行创建
  doConfirmActionItems(userId, documentId)
}

async function doConfirmActionItems(userId, documentId) {
  isConfirming.value = true

  try {
    const reminderTimes = {}
    selectedActionItems.value.forEach(idx => {
      if (actionItemDates.value[idx]) {
        reminderTimes[idx] = actionItemDates.value[idx].toISOString()
      }
    })

    const requestBody = {
      user_id: userId,
      document_id: documentId,
      selected_indices: selectedActionItems.value,
      reminder_times: reminderTimes
    }

    console.log('Request body:', requestBody)

    const response = await fetch('/api/documents/confirm-actions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    })

    console.log('Response status:', response.status)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Error response:', errorText)
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }

    const result = await response.json()
    console.log('Response:', result)

    if (result.success) {
      ElMessage.success(`成功创建 ${result.data?.created_count || 0} 个提醒`)
      // 显示警告信息（如未配置飞书）
      if (result.warning) {
        ElMessage.warning(result.warning)
      }
      showUploadDialog.value = false
      // 不清空 uploadResult，保留分析结果以便重新查看
      selectedFile.value = null
      selectedActionItems.value = []
      actionItemDates.value = {}
    } else {
      throw new Error(result.error || '创建失败')
    }
  } catch (error) {
    console.error('Confirm action error:', error)
    ElMessage.error(error.message || '创建提醒失败')
  } finally {
    isConfirming.value = false
  }
}
</script>

<style scoped lang="scss">
.chat-view {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.14), transparent 28%),
    radial-gradient(circle at top right, rgba(251, 146, 60, 0.08), transparent 24%),
    linear-gradient(180deg, #07111f 0%, #0b1324 48%, #0a1423 100%);
}

.session-sidebar {
  position: absolute;
  top: 20px;
  left: 20px;
  bottom: 20px;
  z-index: 30;
  width: min(360px, calc(100vw - 40px));
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(127, 156, 191, 0.18);
  border-radius: 26px;
  background: rgba(9, 18, 33, 0.94);
  box-shadow: 0 24px 80px rgba(2, 6, 23, 0.42);
  backdrop-filter: blur(22px);
  transform: translateX(calc(-100% - 28px));
  transition: transform 0.28s ease, box-shadow 0.28s ease;

  &.open {
    transform: translateX(0);
  }
}

.session-backdrop {
  position: absolute;
  inset: 0;
  z-index: 20;
  border: none;
  background: linear-gradient(90deg, rgba(2, 6, 23, 0.72), rgba(2, 6, 23, 0.24) 38%, rgba(2, 6, 23, 0.08) 65%, transparent);
  cursor: pointer;
}

.session-backdrop-fade-enter-active,
.session-backdrop-fade-leave-active {
  transition: opacity 0.2s ease;
}

.session-backdrop-fade-enter-from,
.session-backdrop-fade-leave-to {
  opacity: 0;
}

.session-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 22px 18px;
  border-bottom: 1px solid rgba(127, 156, 191, 0.12);
}

.session-header-copy {
  min-width: 0;
}

.session-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-new-button {
  border-radius: 14px;
}

.session-close-button {
  color: #8ea3bf;
}

.session-title {
  color: #f8fbff;
  font-size: 18px;
  font-weight: 700;
}

.session-subtitle {
  margin-top: 4px;
  color: #7f93ad;
  font-size: 12px;
}

.session-loading,
.session-empty {
  padding: 20px 22px;
  color: #9db0c8;
  font-size: 13px;
}

.session-search {
  padding: 16px 22px 0;

  :deep(.el-input__wrapper) {
    background: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(127, 156, 191, 0.12);
    box-shadow: none;
  }

  :deep(.el-input__inner) {
    color: #eef6ff;

    &::placeholder {
      color: #6f88a7;
    }
  }
}

.session-empty-title {
  color: #eef6ff;
  font-weight: 600;
  margin-bottom: 6px;
}

.session-empty-text {
  line-height: 1.5;
}

.session-sections {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 18px 18px;
}

.session-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.session-overview-card {
  padding: 12px 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(93, 119, 151, 0.14);
  background: linear-gradient(180deg, rgba(16, 29, 50, 0.74) 0%, rgba(11, 20, 35, 0.9) 100%);
}

.session-overview-label {
  color: #7f93ad;
  font-size: 11px;
}

.session-overview-value {
  margin-top: 8px;
  color: #f4fbff;
  font-size: 20px;
  font-weight: 700;
}

.session-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.session-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #d4e3f5;
  font-size: 13px;
  font-weight: 600;
  padding: 0 4px;
}

.session-section-header.toggle {
  width: 100%;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0 4px;
}

.session-section-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-section-count {
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(53, 73, 102, 0.85);
  color: #c6d7ea;
  font-size: 11px;
}

.toggle-icon {
  color: #7f93ad;
  transition: transform 0.2s ease;

  &.expanded {
    transform: rotate(180deg);
  }
}

.session-section-empty {
  padding: 10px 4px;
  color: #6f88a7;
  font-size: 12px;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item {
  width: 100%;
  padding: 16px;
  border: 1px solid rgba(93, 119, 151, 0.18);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(14, 24, 42, 0.94) 0%, rgba(9, 18, 33, 0.9) 100%);
  transition: all 0.2s ease;

  &:hover {
    border-color: rgba(94, 234, 212, 0.28);
    background: linear-gradient(180deg, rgba(16, 29, 50, 0.98) 0%, rgba(11, 22, 39, 0.94) 100%);
    box-shadow: 0 16px 30px rgba(2, 6, 23, 0.2);
  }

  &.active {
    border-color: rgba(94, 234, 212, 0.55);
    background: linear-gradient(180deg, rgba(15, 48, 62, 0.68) 0%, rgba(12, 28, 44, 0.94) 100%);
    box-shadow: 0 0 0 1px rgba(94, 234, 212, 0.12);
  }

  &.archived-item {
    border-color: rgba(93, 119, 151, 0.12);
    background: rgba(10, 18, 30, 0.66);
  }
}

.session-item-body {
  width: 100%;
  border: none;
  background: transparent;
  padding: 0;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.archived-body {
  cursor: default;
}

.session-item-title {
  color: #f6fbff;
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.session-item-heading-badges {
  display: flex;
  align-items: center;
  gap: 6px;
}

.session-item-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(94, 234, 212, 0.12);
  color: #8cf3e3;
  font-size: 11px;
  font-weight: 600;

  &.muted {
    background: rgba(127, 156, 191, 0.12);
    color: #a8bfd9;
  }
}

.icon-badge {
  gap: 4px;
}

.session-item-preview {
  color: #8fa4be;
  font-size: 12px;
  line-height: 1.5;
  min-height: 36px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.session-item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 10px;
  color: #6d85a3;
  font-size: 11px;
}

.session-item-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(93, 119, 151, 0.14);
}

.chat-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px;
  min-width: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 24px;
  background: rgba(8, 18, 34, 0.78);
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.18);
  backdrop-filter: blur(18px);
}

.chat-header-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.session-toggle {
  width: 48px;
  height: 48px;
  border: 1px solid rgba(127, 156, 191, 0.18);
  border-radius: 16px;
  background: rgba(14, 26, 45, 0.86);
  color: #d8ecff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: rgba(94, 234, 212, 0.32);
    color: #5eead4;
    transform: translateY(-1px);
  }
}

.chat-heading {
  min-width: 0;
}

.chat-heading-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #eef6ff;

  .el-icon {
    color: #5eead4;
  }
}

.chat-pill {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(94, 234, 212, 0.1);
  color: #8cf3e3;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.chat-session-title {
  margin-top: 4px;
  color: #ffffff;
  font-size: 17px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-session-meta {
  margin-top: 4px;
  color: #7f93ad;
  font-size: 12px;
}

.status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(11, 24, 40, 0.76);
  border: 1px solid rgba(127, 156, 191, 0.12);
  font-size: 13px;
  color: #bfd3e8;
  flex-shrink: 0;

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #2dd4bf;
    box-shadow: 0 0 0 6px rgba(45, 212, 191, 0.12);
    animation: pulse 2s infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 6px 4px 0;

  &.empty {
    display: flex;
    overflow: hidden;
    padding: 0;
  }
}

.chat-messages-track {
  max-width: 980px;
  min-height: 100%;
  margin: 0 auto;
  padding: 8px 6px 24px;

  &.empty {
    flex: 1;
    max-width: 1120px;
    display: flex;
    align-items: stretch;
    padding: 0;
  }
}

.welcome-message {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  width: 100%;
  padding: 22px 24px 18px;
  border: 1px solid rgba(127, 156, 191, 0.12);
  border-radius: 28px;
  background: linear-gradient(180deg, rgba(10, 21, 38, 0.86) 0%, rgba(11, 19, 34, 0.72) 100%);
  box-shadow: 0 20px 40px rgba(2, 6, 23, 0.16);

  .welcome-badge {
    display: inline-flex;
    align-items: center;
    height: 28px;
    padding: 0 12px;
    border-radius: 999px;
    margin-bottom: 12px;
    background: rgba(94, 234, 212, 0.08);
    color: #8cf3e3;
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h3 {
    font-size: 22px;
    margin: 8px 0 6px;
    color: #f1f7ff;
  }

  p {
    color: #8ea3bf;
    max-width: 760px;
    margin: 0 auto 14px;
    font-size: 14px;
    line-height: 1.5;
  }
}

.welcome-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 12px;
  max-width: 1120px;
  margin: 0 auto;
  text-align: left;
}

.welcome-card {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(127, 156, 191, 0.12);
  background: rgba(11, 22, 39, 0.7);
}

.welcome-card-title {
  margin-bottom: 8px;
  color: #f1f7ff;
  font-size: 14px;
  font-weight: 700;
}

.welcome-card-subtitle {
  margin-bottom: 10px;
  color: #89a1bf;
  font-size: 12px;
  line-height: 1.45;
}

.starter-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.starter-item {
  width: 100%;
  min-height: 112px;
  padding: 12px 12px;
  text-align: left;
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(14, 26, 45, 0.88) 0%, rgba(11, 20, 35, 0.78) 100%);
  color: inherit;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: rgba(94, 234, 212, 0.28);
    transform: translateY(-1px);
    box-shadow: 0 16px 30px rgba(2, 6, 23, 0.16);
  }
}

.starter-item-title {
  color: #eef6ff;
  font-size: 13px;
  font-weight: 700;
}

.starter-item-text {
  margin-top: 4px;
  color: #8ea3bf;
  font-size: 12px;
  line-height: 1.45;
}

.welcome-capabilities {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.capability-item {
  padding: 8px 0;
  border-top: 1px solid rgba(127, 156, 191, 0.1);

  &:first-child {
    padding-top: 0;
    border-top: none;
  }
}

.capability-title {
  color: #edf7ff;
  font-size: 12px;
  font-weight: 600;
}

.capability-text {
  margin-top: 2px;
  color: #8ea3bf;
  font-size: 11px;
  line-height: 1.4;
}

.message {
  display: flex;
  gap: 14px;
  max-width: 86%;
  margin-bottom: 18px;
  animation: fadeIn 0.3s ease;

  &.user {
    flex-direction: row-reverse;
    margin-left: auto;

    .el-avatar {
      background: linear-gradient(135deg, #38bdf8, #0ea5e9);
    }

    .message-content {
      background: linear-gradient(135deg, #0f4c81, #0b6ba8);
      border-radius: 22px 22px 8px 22px;
    }
  }

  &.assistant {
    .el-avatar {
      background: linear-gradient(135deg, #13253f, #0f1d31);
    }

    .message-content {
      background: linear-gradient(180deg, rgba(15, 26, 43, 0.96) 0%, rgba(13, 22, 37, 0.92) 100%);
      border: 1px solid rgba(127, 156, 191, 0.12);
      border-radius: 22px 22px 22px 8px;
    }
  }

  &.error .message-content {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.3);
  }

  &.typing .message-content {
    display: flex;
    align-items: center;
    min-height: 44px;
  }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-content {
  padding: 15px 18px;
  color: #f2f7fd;
  box-shadow: 0 18px 32px rgba(2, 6, 23, 0.12);

  .message-text {
    line-height: 1.72;
    font-size: 15px;

    :deep(p) {
      margin: 0 0 8px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    :deep(code) {
      background: rgba(0, 0, 0, 0.3);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
    }

    :deep(ul),
    :deep(ol) {
      padding-left: 20px;
    }
  }

  .message-time {
    font-size: 11px;
    color: rgba(226, 239, 255, 0.54);
    margin-top: 8px;
    text-align: right;
  }

  .analysis-actions {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);

    .el-button {
      font-size: 13px;

      .el-icon {
        margin-right: 4px;
      }
    }
  }
}

.typing-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.chat-input-area {
  max-width: 980px;
  margin: 0 auto;
  padding: 16px 18px;
  border: 1px solid rgba(127, 156, 191, 0.14);
  border-radius: 24px;
  background: rgba(8, 18, 34, 0.82);
  box-shadow: 0 20px 48px rgba(2, 6, 23, 0.22);
  backdrop-filter: blur(18px);
}

.chat-input-shell {
  padding-top: 2px;
}

.input-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;

  .el-button {
    height: 36px;
    padding: 0 14px;
    border-radius: 999px;
    background: rgba(16, 28, 46, 0.78);
    color: #a5bdd8;
    border: 1px solid rgba(127, 156, 191, 0.12);

    &:hover {
      color: #5eead4;
      border-color: rgba(94, 234, 212, 0.26);
    }
  }
}

.input-group {
  display: flex;
  gap: 12px;
  align-items: flex-end;

  .el-textarea {
    flex: 1;

    :deep(.el-textarea__inner) {
      min-height: 52px !important;
      padding: 14px 16px;
      background: rgba(13, 24, 40, 0.84);
      border-color: rgba(127, 156, 191, 0.14);
      color: #f1f7ff;
      box-shadow: none;

      &:focus {
        border-color: rgba(94, 234, 212, 0.34);
      }

      &::placeholder {
        color: #6f88a7;
      }
    }
  }

  .el-button {
    height: 52px;
    width: 52px;
    padding: 0;
    border-radius: 16px;
  }
}

.input-footer {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #6f88a7;
  font-size: 12px;
}

.search-results {
  margin-top: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.search-result-item {
  margin-bottom: 12px;
  background: rgba(51, 65, 85, 0.3);
  border: 1px solid #334155;

  .result-score {
    font-size: 12px;
    color: #6366f1;
    margin-bottom: 8px;

    .el-icon {
      margin-right: 4px;
    }
  }

  .result-content {
    color: #f1f5f9;
    font-size: 14px;
    line-height: 1.5;
  }
}

// 文件上传样式
.upload-area {
  .document-uploader {
    :deep(.el-upload) {
      width: 100%;
    }

    :deep(.el-upload-dragger) {
      background: rgba(51, 65, 85, 0.3);
      border-color: #475569;
      width: 100%;
      padding: 40px 20px;

      &:hover {
        border-color: #6366f1;
      }

      .el-icon--upload {
        font-size: 48px;
        color: #6366f1;
        margin-bottom: 16px;
      }

      .el-upload__text {
        color: #94a3b8;

        em {
          color: #6366f1;
        }
      }

      .el-upload__tip {
        color: #64748b;
      }
    }
  }
}

.upload-progress {
  margin-top: 20px;
}

.selected-file-info {
  margin-top: 16px;
}

.upload-complete {
  margin-top: 20px;
}

// 处理进度样式
.processing-area {
  padding: 40px 20px;
  text-align: center;

  .processing-header {
    margin-bottom: 24px;

    .processing-icon {
      animation: spin 1s linear infinite;
      margin-bottom: 16px;
    }

    h4 {
      color: #f1f5f9;
      font-size: 18px;
      margin: 0 0 8px;
    }

    .processing-stage {
      color: #94a3b8;
      margin: 0 0 8px;
    }

    .processing-hint {
      color: #64748b;
      font-size: 12px;
      margin: 0;
    }
  }

  .processing-details {
    margin-top: 16px;
  }
}

// 结果展示样式
.result-area {
  max-height: 500px;
  overflow-y: auto;

  .result-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #334155;

    h4 {
      color: #f1f5f9;
      margin: 0;
    }
  }

  .result-content {
    :deep(.el-descriptions) {
      background: rgba(51, 65, 85, 0.3);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 20px;

      .el-descriptions__label {
        color: #94a3b8;
      }

      .el-descriptions__content {
        color: #f1f5f9;
      }
    }

    .result-section {
      margin-bottom: 20px;

      h5 {
        color: #6366f1;
        font-size: 14px;
        margin: 0 0 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #334155;
      }

      .summary-text {
        color: #f1f5f9;
        line-height: 1.6;
        margin: 0;
      }

      .decision-list {
        margin: 0;
        padding-left: 20px;
        color: #f1f5f9;

        li {
          margin-bottom: 8px;
          line-height: 1.5;
        }
      }

      .action-item {
        margin-bottom: 12px;

        .action-item-content {
          display: flex;
          flex-direction: column;
          gap: 4px;

          .action-text {
            color: #f1f5f9;
          }

          .action-assignee {
            color: #6366f1;
            font-size: 12px;
          }
        }
      }
    }
  }
}

:deep(.el-checkbox) {
  color: #f1f5f9;

  .el-checkbox__label {
    color: #f1f5f9;
  }
}

@media (max-width: 960px) {
  .chat-view {
    padding: 0;
  }

  .session-sidebar {
    top: 12px;
    left: 12px;
    bottom: 12px;
    width: calc(100vw - 24px);
  }

  .session-list {
    max-height: 220px;
  }

  .session-overview {
    grid-template-columns: 1fr;
  }

  .session-sidebar-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .session-header-actions {
    width: 100%;
  }

  .session-new-button {
    flex: 1;
  }

  .chat-panel {
    padding: 12px;
    gap: 12px;
  }

  .chat-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .chat-header-main {
    width: 100%;
  }

  .chat-heading-top {
    flex-wrap: wrap;
  }

  .chat-session-title {
    white-space: normal;
  }

  .welcome-grid {
    grid-template-columns: 1fr;
  }

  .starter-list {
    grid-template-columns: 1fr;
  }

  .message {
    max-width: 100%;
  }

  .chat-messages-track {
    padding-bottom: 12px;
  }

  .chat-input-area {
    padding: 14px;
  }

  .input-group {
    gap: 10px;
  }

  .input-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .input-group .el-button {
    width: 48px;
    height: 48px;
  }
}

@media (max-width: 1280px) {
  .starter-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
