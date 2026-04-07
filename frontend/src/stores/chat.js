import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { useUserStore } from './user'

function createLocalId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

function loadSessionId() {
  return localStorage.getItem('memorymate_chat_session_id') || ''
}

function persistSessionId(sessionId) {
  if (!sessionId) return
  localStorage.setItem('memorymate_chat_session_id', sessionId)
}

function clearPersistedSessionId() {
  localStorage.removeItem('memorymate_chat_session_id')
}

function formatMessageTime(value) {
  if (!value) return new Date().toLocaleTimeString()
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return new Date().toLocaleTimeString()
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function buildMessageMergeKey(message) {
  if (message?.turnId && message?.role) {
    return `turn:${message.turnId}:${message.role}`
  }
  if (message?.id) {
    return `id:${message.id}`
  }
  return `content:${message?.role || 'unknown'}:${message?.content || ''}`
}

function sortMessagesByCreatedAt(messagesList) {
  return [...messagesList].sort((left, right) => {
    const leftTime = Date.parse(left?.createdAt || '') || 0
    const rightTime = Date.parse(right?.createdAt || '') || 0
    if (leftTime !== rightTime) {
      return leftTime - rightTime
    }
    return String(left?.id || '').localeCompare(String(right?.id || ''))
  })
}

function mergeSessionMessages(existingMessages, loadedMessages) {
  const merged = [...loadedMessages]
  const loadedKeys = new Set(loadedMessages.map(buildMessageMergeKey))

  for (const message of existingMessages || []) {
    const messageKey = buildMessageMergeKey(message)
    if (!loadedKeys.has(messageKey)) {
      merged.push(message)
    }
  }

  return sortMessagesByCreatedAt(merged)
}

export const useChatStore = defineStore('chat', () => {
  const sessionMessages = ref({})
  const sessions = ref([])
  const pendingSessionIds = ref([])
  const sessionsLoading = ref(false)
  const currentSessionId = ref(loadSessionId())
  const sessionLoadTokens = ref({})
  const messages = computed(() => {
    return sessionMessages.value[currentSessionId.value] || []
  })
  const isTyping = computed(() => {
    return currentSessionId.value ? pendingSessionIds.value.includes(currentSessionId.value) : false
  })
  const activeSessions = computed(() => {
    return sessions.value.filter((session) => session.status !== 'archived')
  })
  const archivedSessions = computed(() => {
    return sessions.value.filter((session) => session.status === 'archived')
  })
  let sessionSelectionVersion = 0

  function bumpSessionSelectionVersion() {
    sessionSelectionVersion += 1
    return sessionSelectionVersion
  }

  function createSessionLoadToken(sessionId) {
    const nextToken = (sessionLoadTokens.value[sessionId] || 0) + 1
    sessionLoadTokens.value = {
      ...sessionLoadTokens.value,
      [sessionId]: nextToken
    }
    return nextToken
  }

  function isSessionTyping(sessionId) {
    return !!sessionId && pendingSessionIds.value.includes(sessionId)
  }

  function setSessionMessages(sessionId, messagesList) {
    if (!sessionId) return
    sessionMessages.value = {
      ...sessionMessages.value,
      [sessionId]: messagesList
    }
  }

  function appendMessageToSession(sessionId, message) {
    if (!sessionId) return
    const nextMessages = [...(sessionMessages.value[sessionId] || []), message]
    setSessionMessages(sessionId, nextMessages)
  }

  function beginTyping(sessionId) {
    if (!sessionId || pendingSessionIds.value.includes(sessionId)) return
    pendingSessionIds.value = [...pendingSessionIds.value, sessionId]
  }

  function endTyping(sessionId) {
    if (!sessionId) return
    pendingSessionIds.value = pendingSessionIds.value.filter((item) => item !== sessionId)
  }

  async function fetchSessions() {
    const userStore = useUserStore()
    if (!userStore.userId) return []

    sessionsLoading.value = true
    try {
      const response = await axios.get(`/api/users/${userStore.userId}/sessions`, {
        params: {
          limit: 100,
          include_archived: true
        }
      })
      sessions.value = response.data.success ? response.data.data : []
      return sessions.value
    } catch (error) {
      console.error('加载会话失败:', error)
      return []
    } finally {
      sessionsLoading.value = false
    }
  }

  async function createSession(title = '新对话') {
    const userStore = useUserStore()
    const response = await axios.post('/api/sessions', {
      user_id: userStore.userId,
      title
    })

    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || '创建会话失败')
    }

    const created = response.data.data
    bumpSessionSelectionVersion()
    currentSessionId.value = created.session_id
    persistSessionId(created.session_id)
    setSessionMessages(created.session_id, [])
    await fetchSessions()
    return created
  }

  async function renameSession(sessionId, title) {
    const userStore = useUserStore()
    const response = await axios.patch(`/api/users/${userStore.userId}/sessions/${sessionId}`, {
      title
    })

    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || '重命名会话失败')
    }

    await fetchSessions()
    return response.data.data
  }

  async function archiveSession(sessionId) {
    const userStore = useUserStore()
    const response = await axios.patch(`/api/users/${userStore.userId}/sessions/${sessionId}`, {
      status: 'archived'
    })

    if (!response.data.success) {
      throw new Error(response.data.error || '归档会话失败')
    }

    if (currentSessionId.value === sessionId) {
      currentSessionId.value = ''
      clearPersistedSessionId()
      await ensureActiveSession()
      return
    }

    await fetchSessions()
  }

  async function restoreSession(sessionId) {
    const userStore = useUserStore()
    const response = await axios.patch(`/api/users/${userStore.userId}/sessions/${sessionId}`, {
      status: 'active'
    })

    if (!response.data.success) {
      throw new Error(response.data.error || '恢复会话失败')
    }

    await fetchSessions()
    return response.data.data
  }

  async function deleteSession(sessionId) {
    const userStore = useUserStore()
    const response = await axios.delete(`/api/users/${userStore.userId}/sessions/${sessionId}`)

    if (!response.data.success) {
      throw new Error(response.data.error || '删除会话失败')
    }

    if (currentSessionId.value === sessionId) {
      currentSessionId.value = ''
      clearPersistedSessionId()
      await ensureActiveSession()
      return
    }

    await fetchSessions()
  }

  async function loadSessionMessages(sessionId) {
    const userStore = useUserStore()
    if (!userStore.userId || !sessionId) {
      if (sessionId) {
        setSessionMessages(sessionId, [])
      }
      return
    }

    const loadToken = createSessionLoadToken(sessionId)
    const response = await axios.get(`/api/users/${userStore.userId}/sessions/${sessionId}/messages?limit=500`)
    if (!response.data.success) {
      throw new Error(response.data.error || '加载会话消息失败')
    }

    if (sessionLoadTokens.value[sessionId] !== loadToken) {
      return
    }

    const loadedMessages = response.data.data.map((message) => ({
      id: message.id,
      turnId: message.turn_id,
      sessionId: message.session_id,
      role: message.role,
      content: message.content,
      time: formatMessageTime(message.created_at),
      createdAt: message.created_at
    }))

    const existingMessages = sessionMessages.value[sessionId] || []
    setSessionMessages(sessionId, mergeSessionMessages(existingMessages, loadedMessages))
  }

  async function switchSession(sessionId) {
    const selectionVersion = bumpSessionSelectionVersion()
    currentSessionId.value = sessionId
    persistSessionId(sessionId)
    await loadSessionMessages(sessionId)
    if (selectionVersion !== sessionSelectionVersion) {
      return
    }
    await fetchSessions()
  }

  async function ensureActiveSession() {
    const userStore = useUserStore()
    if (!userStore.userId) return

    const selectionVersion = sessionSelectionVersion
    const sessionList = await fetchSessions()
    if (selectionVersion !== sessionSelectionVersion) {
      return
    }

    if (!currentSessionId.value) {
      if (activeSessions.value.length > 0) {
        await switchSession(activeSessions.value[0].session_id)
        return
      }
      await createSession()
      return
    }

    const existing = sessionList.find((item) => item.session_id === currentSessionId.value)
    if (existing && existing.status !== 'archived') {
      await loadSessionMessages(currentSessionId.value)
      return
    }

    if (activeSessions.value.length > 0) {
      await switchSession(activeSessions.value[0].session_id)
      return
    }

    await createSession()
  }

  async function startNewSession() {
    await createSession()
  }

  async function sendMessage(content) {
    const userStore = useUserStore()
    if (!content.trim()) return
    if (!currentSessionId.value) {
      await ensureActiveSession()
    }

    const requestSessionId = currentSessionId.value
    if (isSessionTyping(requestSessionId)) return
    const turnId = createLocalId('turn')
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    appendMessageToSession(requestSessionId, {
      id: turnId,
      turnId,
      sessionId: requestSessionId,
      role: 'user',
      content,
      time: now,
      createdAt: new Date().toISOString()
    })
    beginTyping(requestSessionId)

    try {
      const response = await axios.post('/api/chat', {
        user_id: userStore.userId,
        message: content,
        stream: false,
        session_id: requestSessionId,
        turn_id: turnId
      })

      if (response.data.success) {
        const responseSessionId = response.data.session_id || requestSessionId

        appendMessageToSession(responseSessionId, {
          id: `${turnId}_assistant`,
          turnId: response.data.turn_id || turnId,
          sessionId: responseSessionId,
          role: 'assistant',
          content: response.data.data,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          createdAt: new Date().toISOString()
        })

        await fetchSessions()
        loadSessionMessages(responseSessionId).catch((error) => {
          console.error('同步会话消息失败:', error)
        })
      } else {
        appendMessageToSession(requestSessionId, {
          id: `${turnId}_assistant_error`,
          turnId,
          sessionId: requestSessionId,
          role: 'assistant',
          content: `抱歉，出现了错误: ${response.data.error || '未知错误'}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          error: true
        })
      }
    } catch (error) {
      appendMessageToSession(requestSessionId, {
        id: `${turnId}_assistant_error`,
        turnId,
        sessionId: requestSessionId,
        role: 'assistant',
        content: '抱歉，服务暂时不可用，请稍后重试。',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        error: true
      })
    } finally {
      endTyping(requestSessionId)
    }
  }

  async function clearChat() {
    const userStore = useUserStore()
    try {
      if (currentSessionId.value) {
        await axios.post('/api/clear', {
          user_id: userStore.userId,
          session_id: currentSessionId.value
        })
      }
      await startNewSession()
    } catch (error) {
      console.error('清空对话失败:', error)
    }
  }

  function resetState() {
    bumpSessionSelectionVersion()
    sessionMessages.value = {}
    sessions.value = []
    pendingSessionIds.value = []
    sessionLoadTokens.value = {}
    sessionsLoading.value = false
    currentSessionId.value = ''
    clearPersistedSessionId()
  }

  return {
    messages,
    sessionMessages,
    sessions,
    activeSessions,
    archivedSessions,
    isTyping,
    isSessionTyping,
    sessionsLoading,
    currentSessionId,
    appendMessageToSession,
    fetchSessions,
    createSession,
    renameSession,
    archiveSession,
    restoreSession,
    deleteSession,
    loadSessionMessages,
    switchSession,
    ensureActiveSession,
    sendMessage,
    clearChat,
    startNewSession,
    resetState
  }
})
