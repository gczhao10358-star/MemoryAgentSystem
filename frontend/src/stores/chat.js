import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { useUserStore } from './user'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isTyping = ref(false)

  async function sendMessage(content) {
    const userStore = useUserStore()
    if (!content.trim() || isTyping.value) return

    // 添加用户消息
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content,
      time: new Date().toLocaleTimeString()
    }
    messages.value.push(userMessage)
    isTyping.value = true

    try {
      const response = await axios.post('/api/chat', {
        user_id: userStore.userId,
        message: content,
        stream: false
      })

      if (response.data.success) {
        messages.value.push({
          id: Date.now() + 1,
          role: 'assistant',
          content: response.data.data,
          time: new Date().toLocaleTimeString()
        })
      } else {
        messages.value.push({
          id: Date.now() + 1,
          role: 'assistant',
          content: `抱歉，出现了错误: ${response.data.error || '未知错误'}`,
          time: new Date().toLocaleTimeString(),
          error: true
        })
      }
    } catch (error) {
      messages.value.push({
        id: Date.now() + 1,
        role: 'assistant',
        content: '抱歉，服务暂时不可用，请稍后重试。',
        time: new Date().toLocaleTimeString(),
        error: true
      })
    } finally {
      isTyping.value = false
    }
  }

  async function clearChat() {
    const userStore = useUserStore()
    try {
      await axios.post('/api/clear', { user_id: userStore.userId })
      messages.value = []
    } catch (error) {
      console.error('清空对话失败:', error)
    }
  }

  return {
    messages,
    isTyping,
    sendMessage,
    clearChat
  }
})
