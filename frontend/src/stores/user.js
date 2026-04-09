import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  // State
  const userId = ref(localStorage.getItem('memorymate_user_id') || '')
  const username = ref(localStorage.getItem('memorymate_username') || '')
  const isLoading = ref(false)

  // Getters
  const isLoggedIn = computed(() => !!userId.value)

  // Actions
  async function createUser(name) {
    isLoading.value = true
    try {
      const response = await axios.post('/api/users', { username: name })
      if (response.data.success) {
        userId.value = response.data.user_id
        username.value = response.data.username
        localStorage.setItem('memorymate_user_id', userId.value)
        localStorage.setItem('memorymate_username', username.value)
        return { success: true }
      }
      return { success: false, error: response.data.error }
    } catch (error) {
      return { success: false, error: error.message }
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    userId.value = ''
    username.value = ''
    localStorage.removeItem('memorymate_user_id')
    localStorage.removeItem('memorymate_username')
  }

  return {
    userId,
    username,
    isLoading,
    isLoggedIn,
    createUser,
    logout
  }
})
