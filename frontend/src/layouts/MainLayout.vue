<template>
  <el-container class="main-layout">
    <el-aside width="260px" class="sidebar">
      <div class="sidebar-header">
        <el-icon size="28" color="#6366f1"><Cpu /></el-icon>
        <span class="title">智忆助理</span>
      </div>

      <div class="user-info">
        <el-avatar :size="48" class="user-avatar">
          <el-icon><UserFilled /></el-icon>
        </el-avatar>
        <div class="user-details">
          <span class="username">{{ userStore.username }}</span>
          <span class="user-id">ID: {{ userStore.userId.slice(0, 8) }}</span>
        </div>
      </div>

      <el-menu
        :default-active="$route.path"
        class="sidebar-menu"
        router
        background-color="transparent"
        text-color="#94a3b8"
        active-text-color="#6366f1"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="current-time" v-if="currentTime">
          <el-icon><Clock /></el-icon>
          <div class="time-info">
            <span class="date">{{ currentTime.date }}</span>
            <span class="weekday">{{ currentTime.weekday_name }} {{ currentTime.time }}</span>
          </div>
        </div>
        <el-button type="info" plain @click="handleClearChat">
          <el-icon><Delete /></el-icon>
          清空对话
        </el-button>
        <el-button type="danger" text @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          退出
        </el-button>
      </div>
    </el-aside>

    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { Cpu, UserFilled, Delete, SwitchButton, Clock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'
import axios from 'axios'

// 临时存储用户ID，用于组件卸载后仍能在onUnmounted中访问
let currentUserId = null

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const chatStore = useChatStore()
const currentTime = ref(null)
let timeTimer = null

// 获取当前时间
async function fetchCurrentTime() {
  try {
    const { data } = await axios.get('/api/now')
    if (data.success) {
      currentTime.value = data.data
    }
  } catch (e) {
    console.error('Failed to fetch current time:', e)
  }
}

onMounted(() => {
  fetchCurrentTime()
  // 每分钟刷新一次时间
  timeTimer = setInterval(fetchCurrentTime, 60000)
  // 延迟连接WebSocket，确保用户状态已加载
  setTimeout(() => {
    connectReminderWebSocket()
  }, 500)
})

onUnmounted(() => {
  if (timeTimer) {
    clearInterval(timeTimer)
  }
  // 断开WebSocket
  disconnectReminderWebSocket()
})

// WebSocket连接（用于接收提醒）
let reminderWs = null
let reconnectTimer = null
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_INTERVAL = 3000

function connectReminderWebSocket() {
  if (!userStore.userId) {
    console.log('[WebSocket] 用户未登录，暂不连接')
    return
  }

  // 避免重复连接
  if (reminderWs && (reminderWs.readyState === WebSocket.CONNECTING || reminderWs.readyState === WebSocket.OPEN)) {
    console.log('[WebSocket] 已存在连接，跳过')
    return
  }

  // 使用ws协议，端口8000
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000/ws/${userStore.userId}`
  console.log('[WebSocket] 正在连接:', wsUrl)

  reminderWs = new WebSocket(wsUrl)

  reminderWs.onopen = () => {
    console.log('[WebSocket] 已连接，用户:', userStore.userId)
    reconnectAttempts = 0 // 重置重连次数
    ElMessage.success('已连接到实时通知服务')
  }

  reminderWs.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      console.log('[WebSocket] 收到消息:', data)

      // 处理连接成功消息
      if (data.type === 'connected') {
        console.log('[WebSocket] 连接确认:', data.message)
        if (data.offline_messages > 0) {
          ElMessage.info(`有 ${data.offline_messages} 条离线消息待同步`)
        }
        return
      }

      // 处理心跳
      if (data.type === 'ping') {
        reminderWs.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }))
        return
      }

      // 处理提醒消息
      if (data.type === 'reminder') {
        // 使用通知而非弹窗，避免阻塞
        ElNotification({
          title: data.title || '⏰ 提醒',
          message: data.content,
          type: 'info',
          duration: 0, // 不自动关闭
          showClose: true,
          onClick: () => {
            // 点击通知可以执行某些操作
            console.log('[WebSocket] 用户点击了提醒通知')
          }
        })
        // 同时在聊天中添加一条系统消息（如果存在chatStore）
        if (chatStore && chatStore.messages) {
          chatStore.messages.push({
            id: Date.now(),
            role: 'assistant',
            content: `⏰ **提醒**\n\n${data.content}\n\n*${data.is_offline_message ? '（这是您离线期间的提醒）' : ''}*`,
            time: new Date().toLocaleTimeString()
          })
        }
      }
    } catch (e) {
      console.error('[WebSocket] 解析消息失败:', e)
    }
  }

  reminderWs.onerror = (error) => {
    console.error('[WebSocket] 连接错误:', error)
  }

  reminderWs.onclose = (event) => {
    console.log('[WebSocket] 连接关闭, code:', event.code, 'reason:', event.reason, 'wasClean:', event.wasClean)
    // 尝试重连（如果不是手动断开且不是正常关闭）
    if (event.code !== 1000 && event.code !== 1001 && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++
      console.log(`[WebSocket] ${RECONNECT_INTERVAL/1000}秒后尝试第${reconnectAttempts}次重连...`)
      reconnectTimer = setTimeout(() => {
        connectReminderWebSocket()
      }, RECONNECT_INTERVAL)
    } else if (event.code === 1000 || event.code === 1001) {
      console.log('[WebSocket] 连接正常关闭，不再重连')
    } else {
      console.log('[WebSocket] 达到最大重连次数，停止重连')
      ElMessage.warning('实时通知连接失败，请刷新页面重试')
    }
  }
}

function disconnectReminderWebSocket() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (reminderWs) {
    // 标记为手动断开，不触发重连
    reminderWs.onclose = null
    reminderWs.close()
    reminderWs = null
    console.log('[WebSocket] 已断开')
  }
}

const menuItems = computed(() => {
  return route.matched[0]?.children?.map(child => ({
    path: `/${child.path}`,
    title: child.meta?.title,
    icon: child.meta?.icon
  })) || []
})

async function handleClearChat() {
  try {
    await ElMessageBox.confirm('确定要清空当前对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await chatStore.clearChat()
    ElMessage.success('对话已清空')
  } catch {
    // 用户取消
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    userStore.logout()
    router.push('/login')
    ElMessage.success('已退出登录')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;
  background: #0f172a;
}

.sidebar {
  background: #1e293b;
  border-right: 1px solid #334155;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  gap: 12px;

  .title {
    font-size: 20px;
    font-weight: 700;
    color: #f1f5f9;
  }
}

.user-info {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #334155;
}

.user-avatar {
  background: linear-gradient(135deg, #6366f1, #a855f7);
}

.user-details {
  display: flex;
  flex-direction: column;

  .username {
    font-weight: 600;
    font-size: 15px;
    color: #f1f5f9;
  }

  .user-id {
    font-size: 12px;
    color: #64748b;
  }
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  padding: 16px 12px;

  :deep(.el-menu-item) {
    border-radius: 8px;
    margin-bottom: 4px;

    &:hover {
      background: rgba(51, 65, 85, 0.5);
    }

    &.is-active {
      background: rgba(99, 102, 241, 0.15);
    }
  }
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid #334155;
  display: flex;
  flex-direction: column;
  gap: 8px;

  .el-button {
    justify-content: flex-start;
  }

  .current-time {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    background: rgba(99, 102, 241, 0.1);
    border-radius: 8px;
    margin-bottom: 8px;
    color: #6366f1;

    .el-icon {
      font-size: 20px;
    }

    .time-info {
      display: flex;
      flex-direction: column;
      flex: 1;

      .date {
        font-size: 13px;
        font-weight: 600;
        color: #f1f5f9;
      }

      .weekday {
        font-size: 11px;
        color: #94a3b8;
      }
    }
  }
}

.main-content {
  padding: 0;
  overflow: hidden;
}
</style>
