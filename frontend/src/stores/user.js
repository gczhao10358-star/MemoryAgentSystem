import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  // State
  const userId = ref(localStorage.getItem('memorymate_user_id') || '')
  const username = ref(localStorage.getItem('memorymate_username') || '')
  const isLoading = ref(false)
  const isProfileLoading = ref(false)
  const profile = ref(null)
  let latestProfileRequestToken = 0

  // Getters
  const isLoggedIn = computed(() => !!userId.value)
  const displayName = computed(() => {
    return profile.value?.name || username.value || ''
  })
  const interactionStyle = computed(() => {
    return profile.value?.interaction_style || {}
  })

  function persistAuth() {
    localStorage.setItem('memorymate_user_id', userId.value)
    localStorage.setItem('memorymate_username', username.value)
  }

  function clearAuth() {
    localStorage.removeItem('memorymate_user_id')
    localStorage.removeItem('memorymate_username')
  }

  async function fetchCurrentUser(targetUserId = userId.value) {
    if (!targetUserId) {
      profile.value = null
      return { success: false, error: '用户未登录' }
    }

    const requestToken = ++latestProfileRequestToken
    isProfileLoading.value = true
    try {
      const response = await axios.get(`/api/users/${targetUserId}`)
      if (response.data.success) {
        if (requestToken !== latestProfileRequestToken || userId.value !== targetUserId) {
          return { success: false, error: '用户状态已变化', stale: true }
        }

        const user = response.data.data
        profile.value = user
        userId.value = user.user_id
        username.value = user.username || user.name || ''
        persistAuth()
        return { success: true, data: user }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    } finally {
      if (requestToken === latestProfileRequestToken) {
        isProfileLoading.value = false
      }
    }
  }

  // Actions
  async function createUser(name) {
    isLoading.value = true
    try {
      const response = await axios.post('/api/users', { username: name })
      if (response.data.success) {
        userId.value = response.data.user_id
        username.value = response.data.username
        persistAuth()
        await fetchCurrentUser(userId.value)
        return { success: true }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    } finally {
      isLoading.value = false
    }
  }

  async function updateCurrentUser(payload) {
    if (!userId.value) {
      return { success: false, error: '用户未登录' }
    }

    isLoading.value = true
    try {
      const response = await axios.patch(`/api/users/${userId.value}`, payload)
      if (response.data.success) {
        profile.value = response.data.data
        username.value = response.data.data.username || response.data.data.name || username.value
        persistAuth()
        return { success: true, data: response.data.data }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    } finally {
      isLoading.value = false
    }
  }

  async function hydrateUser() {
    if (!userId.value) {
      profile.value = null
      return { success: false, error: '用户未登录' }
    }

    if (profile.value?.user_id === userId.value) {
      return { success: true, data: profile.value }
    }

    const result = await fetchCurrentUser(userId.value)
    if (!result.success) {
      // 1. 并发场景：被新请求抢占（stale），认为成功并放行
      if (result.stale) {
        return { success: true, data: profile.value || { user_id: userId.value }, stale: true }
      }
      // 2. 仅在后端明确告知"用户不存在"时才登出
      const errMsg = (result.error || '').toString()
      const isUserMissing = /用户不存在|user not found|404/i.test(errMsg)
      if (isUserMissing) {
        logout()
        return result
      }
      // 3. 网络抖动 / 临时错误：保留 userId，按"已登录但画像未加载"放行
      return { success: true, data: profile.value || { user_id: userId.value } }
    }
    return result
  }

  function logout() {
    latestProfileRequestToken += 1
    userId.value = ''
    username.value = ''
    profile.value = null
    clearAuth()
    localStorage.removeItem('memorymate_chat_session_id')
  }

  return {
    userId,
    username,
    isLoading,
    isProfileLoading,
    profile,
    isLoggedIn,
    displayName,
    interactionStyle,
    createUser,
    fetchCurrentUser,
    updateCurrentUser,
    hydrateUser,
    logout
  }
})
