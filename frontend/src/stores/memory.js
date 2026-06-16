import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { useUserStore } from './user'

export const useMemoryStore = defineStore('memory', () => {
  const memories = ref([])
  const searchResults = ref([])
  const isLoading = ref(false)

  async function loadMemories() {
    const userStore = useUserStore()
    isLoading.value = true
    try {
      const response = await axios.get(`/api/users/${userStore.userId}/memories?limit=100`)
      if (response.data.success) {
        memories.value = (response.data.data || []).filter(memory => memory.memory_type !== 'chat')
      }
    } catch (error) {
      console.error('加载记忆失败:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function searchMemories(query) {
    const userStore = useUserStore()
    if (!query.trim()) return

    isLoading.value = true
    try {
      const response = await axios.post('/api/search', {
        user_id: userStore.userId,
        query,
        top_k: 10
      })
      if (response.data.success) {
        searchResults.value = response.data.data
      }
    } catch (error) {
      console.error('搜索记忆失败:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function addMemory(content, type, importance) {
    const userStore = useUserStore()
    try {
      const response = await axios.post('/api/remember', {
        user_id: userStore.userId,
        content,
        memory_type: type,
        importance
      })
      if (response.data.success) {
        await loadMemories()
        return { success: true }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async function deleteMemory(memoryId) {
    const userStore = useUserStore()
    if (!userStore.userId) {
      return { success: false, error: '用户未登录' }
    }
    try {
      const response = await axios.delete(`/api/memories/${memoryId}`, {
        params: { user_id: userStore.userId }
      })
      if (response.data.success) {
        // 本地立即移除，避免再发一次 list 请求
        memories.value = memories.value.filter(m => m.memory_id !== memoryId)
        searchResults.value = searchResults.value.filter(m => m.memory_id !== memoryId)
        return { success: true }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async function updateMemory(memoryId, updates) {
    const userStore = useUserStore()
    if (!userStore.userId) return { success: false, error: '用户未登录' }
    try {
      const response = await axios.put(`/api/memories/${memoryId}`, {
        user_id: userStore.userId,
        ...updates
      })
      if (response.data.success) {
        const idx = memories.value.findIndex(m => m.memory_id === memoryId)
        if (idx >= 0) {
          memories.value[idx] = { ...memories.value[idx], ...updates }
        }
        return { success: true }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async function batchDeleteMemories(memoryIds) {
    const userStore = useUserStore()
    if (!userStore.userId) return { success: false, error: '用户未登录' }
    if (!memoryIds || memoryIds.length === 0) return { success: false, error: '未选择记忆' }
    try {
      const response = await axios.post('/api/memories/batch-delete', {
        user_id: userStore.userId,
        memory_ids: memoryIds
      })
      if (response.data.success) {
        const deletedSet = new Set(response.data.deleted_ids || [])
        memories.value = memories.value.filter(m => !deletedSet.has(m.memory_id))
        searchResults.value = searchResults.value.filter(m => !deletedSet.has(m.memory_id))
        return {
          success: true,
          deleted: response.data.deleted,
          failed: response.data.failed,
          skipped: response.data.skipped
        }
      }
      return { success: false, error: response.data.error || '批量删除失败' }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async function exportMemories(format = 'markdown') {
    const userStore = useUserStore()
    if (!userStore.userId) return { success: false, error: '用户未登录' }
    try {
      const response = await axios.get(
        `/api/users/${userStore.userId}/memories/export`,
        { params: { format } }
      )
      if (response.data.success) {
        return { success: true, data: response.data.data, count: response.data.count }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  return {
    memories,
    searchResults,
    isLoading,
    loadMemories,
    searchMemories,
    addMemory,
    deleteMemory,
    updateMemory,
    batchDeleteMemories,
    exportMemories
  }
})
