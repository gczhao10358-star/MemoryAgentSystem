<template>
  <div class="chat-view">
    <div class="chat-header">
      <div class="title">
        <el-icon><ChatRound /></el-icon>
        <span>智忆助理</span>
      </div>
      <div class="status">
        <span class="status-dot"></span>
        <span>在线</span>
      </div>
    </div>

    <div class="chat-messages" ref="messagesRef">
      <div v-if="chatStore.messages.length === 0" class="welcome-message">
        <el-icon size="64" color="#6366f1"><Cpu /></el-icon>
        <h3>欢迎使用智忆助理!</h3>
        <p>我会记住我们的对话，为您提供个性化的帮助。</p>
        <div class="quick-actions">
          <el-button
            v-for="(item, index) in quickActions"
            :key="index"
            @click="sendQuickMessage(item)"
          >
            {{ item }}
          </el-button>
        </div>
      </div>

      <div
        v-for="message in chatStore.messages"
        :key="message.id"
        :class="['message', message.role, { error: message.error }]"
      >
        <el-avatar :size="36" :class="message.role">
          <el-icon v-if="message.role === 'user'"><UserFilled /></el-icon>
          <el-icon v-else><Cpu /></el-icon>
        </el-avatar>
        <div class="message-content">
          <div class="message-text" v-html="formatMessage(message.content)"></div>
          <!-- 会议解析消息添加查看详情按钮 -->
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
        <el-avatar :size="36" class="assistant">
          <el-icon><Cpu /></el-icon>
        </el-avatar>
        <div class="message-content">
          <el-icon class="typing-icon"><Loading /></el-icon>
        </div>
      </div>
    </div>

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
          @keydown.enter.prevent="handleSend"
        />
        <el-button
          type="primary"
          :disabled="!inputMessage.trim() || chatStore.isTyping"
          @click="handleSend"
        >
          <el-icon><Promotion /></el-icon>
        </el-button>
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
import { ref, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import {
  ChatRound, Cpu, UserFilled, Loading,
  Collection, Search, Promotion, StarFilled,
  Upload, Document, CircleCheck, Warning
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
  '你好，请介绍一下你自己',
  '你能记住什么信息？',
  '帮我记录一个重要的事情'
]

const rememberForm = ref({
  content: '',
  type: 'fact',
  importance: 0.5
})

function formatMessage(content) {
  return marked(content, { breaks: true })
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

function sendQuickMessage(text) {
  inputMessage.value = text
  handleSend()
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
  showUploadDialog.value = true
}

function resetUpload() {
  selectedFile.value = null
  uploadResult.value = null
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

  isUploading.value = true
  uploadProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value.raw)
    formData.append('user_id', userStore.userId)
    formData.append('source', 'web')

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
      ElMessage.info('该文件已上传过，正在获取解析结果...')
    } else {
      console.log('Starting WebSocket connection for document:', result.document_id)
    }

    // 连接 WebSocket 获取处理进度（新文件或已存在文件都走WebSocket）
    connectProcessingWebSocket(result.document_id)

  } catch (error) {
    console.error('Upload error:', error)
    ElMessage.error(error.message || '上传失败')
    isUploading.value = false
  }
}

function connectProcessingWebSocket(documentId) {
  // 使用固定地址而不是 window.location.host 避免一些问题
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = '127.0.0.1:8000'  // 直接使用后端地址
  const wsUrl = `${protocol}//${host}/ws/documents/${documentId}`
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

        // 在对话中显示解析完成的消息
        const meetingTitle = result.meeting_title || '未识别'
        const summary = result.summary || ''
        const summaryPreview = summary ? summary.substring(0, 200) + '...' : '暂无摘要'
        chatStore.messages.push({
          id: Date.now(),
          role: 'assistant',
          content: `📄 会议记录解析完成！\\n\\n**主题：** ${meetingTitle}\\n\\n**摘要：** ${summaryPreview}\\n\\n> 点击上方"查看分析结果"按钮查看详情`,
          time: new Date().toLocaleTimeString()
        })
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
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  padding: 16px 24px;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1e293b;

  .title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;

    .el-icon {
      color: #6366f1;
    }
  }

  .status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #94a3b8;

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      animation: pulse 2s infinite;
    }
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #0f172a;
}

.welcome-message {
  text-align: center;
  padding: 60px 20px;

  h3 {
    font-size: 24px;
    margin: 24px 0 8px;
    color: #f1f5f9;
  }

  p {
    color: #94a3b8;
    margin-bottom: 24px;
  }
}

.quick-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;

  .el-button {
    background: rgba(51, 65, 85, 0.5);
    border-color: #475569;
    color: #f1f5f9;

    &:hover {
      border-color: #6366f1;
    }
  }
}

.message {
  display: flex;
  gap: 12px;
  max-width: 80%;
  margin-bottom: 16px;
  animation: fadeIn 0.3s ease;

  &.user {
    flex-direction: row-reverse;
    margin-left: auto;

    .el-avatar {
      background: linear-gradient(135deg, #6366f1, #a855f7);
    }

    .message-content {
      background: linear-gradient(135deg, #6366f1, #4f46e5);
      border-radius: 16px 16px 4px 16px;
    }
  }

  &.assistant {
    .el-avatar {
      background: #334155;
    }

    .message-content {
      background: #1e293b;
      border-radius: 16px 16px 16px 4px;
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
  padding: 12px 16px;
  color: #f1f5f9;

  .message-text {
    line-height: 1.6;

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
  }

  .message-time {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.5);
    margin-top: 4px;
    text-align: right;
  }

  .analysis-actions {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);

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
  padding: 20px 24px;
  border-top: 1px solid #334155;
  background: #1e293b;
}

.input-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;

  .el-button {
    color: #94a3b8;

    &:hover {
      color: #6366f1;
    }
  }
}

.input-group {
  display: flex;
  gap: 12px;

  .el-textarea {
    flex: 1;

    :deep(.el-textarea__inner) {
      background: rgba(51, 65, 85, 0.5);
      border-color: #475569;
      color: #f1f5f9;

      &:focus {
        border-color: #6366f1;
      }

      &::placeholder {
        color: #64748b;
      }
    }
  }

  .el-button {
    align-self: flex-end;
    height: 44px;
    width: 44px;
    padding: 0;
  }
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
</style>