<template>
  <el-container class="main-layout">
    <el-aside :width="sidebarWidth" :class="['sidebar', { collapsed: sidebarCollapsed }]">
      <div class="sidebar-header">
        <div class="brand-mark">
          <el-icon size="24"><Cpu /></el-icon>
        </div>
        <div v-if="!sidebarCollapsed" class="brand-copy">
          <span class="title">智忆助理</span>
          <span class="subtitle">Memory workspace</span>
        </div>
        <el-button
          text
          circle
          class="collapse-button"
          :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="toggleSidebar"
        >
          <el-icon><component :is="sidebarCollapsed ? Expand : Fold" /></el-icon>
        </el-button>
      </div>

      <div class="user-info">
        <el-avatar :size="50" class="user-avatar">
          <el-icon><UserFilled /></el-icon>
        </el-avatar>
        <div v-if="!sidebarCollapsed" class="user-details">
          <span class="username">{{ userStore.displayName || userStore.username }}</span>
          <span class="user-id">ID {{ userStore.userId.slice(0, 8) }}</span>
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
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
          :title="sidebarCollapsed ? item.title : undefined"
        >
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <span v-if="!sidebarCollapsed">{{ item.title }}</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="current-time" v-if="currentTime">
          <el-icon><Clock /></el-icon>
          <div v-if="!sidebarCollapsed" class="time-info">
            <span class="date">{{ currentTime.date }}</span>
            <span class="weekday">{{ currentTime.weekday_name }} {{ currentTime.time }}</span>
          </div>
        </div>
        <el-button type="info" plain :title="sidebarCollapsed ? '清空对话' : undefined" @click="handleClearChat">
          <el-icon><Delete /></el-icon>
          <span v-if="!sidebarCollapsed">清空对话</span>
        </el-button>
        <el-button type="danger" text :title="sidebarCollapsed ? '退出' : undefined" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span v-if="!sidebarCollapsed">退出</span>
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
import { Cpu, UserFilled, Delete, SwitchButton, Clock, Fold, Expand } from '@element-plus/icons-vue'
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
const SIDEBAR_KEY = 'memorymate_sidebar_collapsed'
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_KEY) === '1')
const sidebarWidth = computed(() => (sidebarCollapsed.value ? '92px' : '228px'))
let timeTickTimer = null
let timeSyncTimer = null
let serverNowBaseMs = null
let serverNowFetchedAtMs = null

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed.value ? '1' : '0')
}

function formatCurrentTime(now) {
  const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const pad = (value) => String(value).padStart(2, '0')

  return {
    iso: now.toISOString(),
    date: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
    time: `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`,
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    day: now.getDate(),
    hour: now.getHours(),
    minute: now.getMinutes(),
    weekday: now.getDay() === 0 ? 6 : now.getDay() - 1,
    weekday_name: weekdayNames[now.getDay() === 0 ? 6 : now.getDay() - 1]
  }
}

function updateDisplayedTime() {
  if (serverNowBaseMs == null || serverNowFetchedAtMs == null) {
    currentTime.value = formatCurrentTime(new Date())
    return
  }

  const elapsedMs = Date.now() - serverNowFetchedAtMs
  currentTime.value = formatCurrentTime(new Date(serverNowBaseMs + elapsedMs))
}

// 获取当前时间
async function fetchCurrentTime() {
  try {
    const { data } = await axios.get('/api/now')
    if (data.success) {
      serverNowBaseMs = Date.parse(data.data.iso)
      serverNowFetchedAtMs = Date.now()
      updateDisplayedTime()
    }
  } catch (e) {
    console.error('Failed to fetch current time:', e)
    if (!currentTime.value) {
      updateDisplayedTime()
    }
  }
}

onMounted(() => {
  userStore.hydrateUser()
  fetchCurrentTime()
  // 本地每秒刷新显示，保证秒级实时变化
  timeTickTimer = setInterval(updateDisplayedTime, 1000)
  // 定期和后端校准一次，避免长时间运行产生漂移
  timeSyncTimer = setInterval(fetchCurrentTime, 60000)
  // 延迟连接WebSocket，确保用户状态已加载
  setTimeout(() => {
    connectReminderWebSocket()
  }, 500)
})

onUnmounted(() => {
  if (timeTickTimer) {
    clearInterval(timeTickTimer)
  }
  if (timeSyncTimer) {
    clearInterval(timeSyncTimer)
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
    disconnectReminderWebSocket()
    chatStore.resetState()
    userStore.logout()
    await router.replace('/login')
    ElMessage.success('已退出登录')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 22%),
    linear-gradient(180deg, #08111e 0%, #0b1424 52%, #0a1321 100%);
}

.sidebar {
  background: linear-gradient(180deg, rgba(10, 18, 31, 0.96) 0%, rgba(11, 20, 35, 0.94) 100%);
  border-right: 1px solid rgba(127, 156, 191, 0.14);
  display: flex;
  flex-direction: column;
  box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.03);
  transition: width 0.24s ease;

  &.collapsed {
    .sidebar-header {
      justify-content: center;
      padding-inline: 12px;
    }

    .user-info {
      justify-content: center;
      padding-inline: 0;
    }

    .sidebar-menu {
      padding-inline: 10px;
    }

    .sidebar-footer {
      align-items: center;
    }

    .current-time {
      justify-content: center;
      width: 52px;
      padding: 12px 0;
    }

    :deep(.el-menu-item) {
      justify-content: center;
      padding: 0 !important;
    }

    .sidebar-footer .el-button {
      width: 52px;
      justify-content: center;
      padding: 0;
    }
  }
}

.sidebar-header {
  padding: 24px 20px 18px;
  border-bottom: 1px solid rgba(127, 156, 191, 0.12);
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.18), rgba(14, 165, 233, 0.2));
  color: #67e8f9;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.title {
  font-size: 18px;
  font-weight: 700;
  color: #f4f8ff;
}

.subtitle {
  margin-top: 2px;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #6f88a7;
}

.collapse-button {
  margin-left: auto;
  color: #8fb0cf;
}

.user-info {
  margin: 16px 16px 0;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid rgba(127, 156, 191, 0.12);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(16, 28, 45, 0.92) 0%, rgba(10, 20, 35, 0.9) 100%);
}

.user-avatar {
  background: linear-gradient(135deg, #38bdf8, #0ea5e9);
}

.user-details {
  display: flex;
  flex-direction: column;
  min-width: 0;

  .username {
    font-weight: 600;
    font-size: 15px;
    color: #f4f8ff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .user-id {
    font-size: 12px;
    color: #6f88a7;
  }
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  padding: 18px 12px 14px;

  :deep(.el-menu-item) {
    height: 48px;
    border-radius: 14px;
    margin-bottom: 6px;
    color: #9fb5cf !important;

    &:hover {
      background: rgba(17, 31, 50, 0.88) !important;
    }

    &.is-active {
      background: linear-gradient(90deg, rgba(94, 234, 212, 0.14), rgba(56, 189, 248, 0.12)) !important;
      color: #e8f7ff !important;
      box-shadow: inset 0 0 0 1px rgba(94, 234, 212, 0.16);
    }
  }

  :deep(.el-menu-item .el-icon) {
    color: inherit;
  }
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(127, 156, 191, 0.12);
  display: flex;
  flex-direction: column;
  gap: 10px;

  .el-button {
    justify-content: flex-start;
    border-radius: 14px;
  }

  .current-time {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 14px;
    background: linear-gradient(180deg, rgba(17, 31, 50, 0.96) 0%, rgba(12, 23, 39, 0.92) 100%);
    border: 1px solid rgba(127, 156, 191, 0.12);
    border-radius: 18px;
    margin-bottom: 4px;
    color: #67e8f9;

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
        color: #f4f8ff;
      }

      .weekday {
        font-size: 11px;
        color: #83a0bf;
      }
    }
  }
}

.main-content {
  padding: 0;
  overflow: hidden;
  background: transparent;
}
</style>
