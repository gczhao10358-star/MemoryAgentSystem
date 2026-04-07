import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { useUserStore } from './user'

export const useStatsStore = defineStore('stats', () => {
  const stats = ref({
    memory: {},
    profile: {}
  })
  const isLoading = ref(false)

  function normalizeStatsPayload(data = {}) {
    const memory = data.memory || {}
    const rawMemoryTypes = memory.memory_types || {}
    const memoryTypes = Object.fromEntries(
      Object.entries(rawMemoryTypes).filter(([type, count]) => type !== 'chat' && Number(count) > 0)
    )
    return {
      memory: {
        total_memories: memory.total_memories || 0,
        session_turns: memory.session_turns ?? memory.legacy?.working_memory_turns ?? memory.working_memory_turns ?? 0,
        cache_entries: memory.cache_entries ?? memory.legacy?.short_term_entries ?? memory.short_term_entries ?? 0,
        memory_types: memoryTypes,
        avg_confidence: memory.avg_confidence || 0,
        avg_importance: memory.avg_importance || 0,
        legacy: memory.legacy || {
          working_memory_turns: memory.working_memory_turns ?? memory.session_turns ?? 0,
          short_term_entries: memory.short_term_entries ?? memory.cache_entries ?? 0
        }
      },
      profile: data.profile || {}
    }
  }

  async function loadStats() {
    const userStore = useUserStore()

    // 确保用户已登录
    if (!userStore.userId) {
      console.log('[Stats] 用户未登录，跳过加载统计')
      return
    }

    isLoading.value = true
    try {
      console.log(`[Stats] 正在加载用户 ${userStore.userId} 的统计数据...`)
      const response = await axios.get(`/api/stats/${userStore.userId}`)
      if (response.data.success) {
        stats.value = normalizeStatsPayload(response.data.data)
        console.log('[Stats] 加载成功:', stats.value)
      } else {
        console.error('[Stats] 加载失败:', response.data.error)
      }
    } catch (error) {
      console.error('加载统计失败:', error)
    } finally {
      isLoading.value = false
    }
  }

  return {
    stats,
    isLoading,
    loadStats
  }
})
