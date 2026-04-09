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
        stats.value = response.data.data
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