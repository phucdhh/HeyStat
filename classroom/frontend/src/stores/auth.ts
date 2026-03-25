import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

interface User {
  id: string
  email: string
  full_name: string | null
  phone?: string | null
  avatar_url?: string | null
  roles: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<User | null>(null)

  const isLoggedIn = computed(() => !!accessToken.value)
  const isTeacher = computed(
    () => user.value?.roles.includes('teacher') || user.value?.roles.includes('admin'),
  )
  const isAdmin = computed(() => user.value?.roles.includes('admin'))

  async function login(email: string, password: string) {
    const { data } = await axios.post('/api/v1/auth/login', { email, password })
    accessToken.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    await fetchMe()
  }

  async function refresh() {
    const { data } = await axios.post('/api/v1/auth/refresh', {}, { withCredentials: true })
    accessToken.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
  }

  async function fetchMe() {
    if (!accessToken.value) return
    const { data } = await axios.get('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${accessToken.value}` },
    })
    user.value = data
  }

  function logout() {
    accessToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
  }

  // Restore session on page reload
  if (accessToken.value && !user.value) {
    fetchMe().catch(() => logout())
  }

  return { accessToken, user, isLoggedIn, isTeacher, isAdmin, login, refresh, fetchMe, logout }
})
