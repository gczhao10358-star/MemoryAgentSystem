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

  return {
    memories,
    searchResults,
    isLoading,
    loadMemories,
    searchMemories,
    addMemory
  }
})
