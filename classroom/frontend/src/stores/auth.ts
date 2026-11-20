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
  // A moderator only reviews shared files; it never unlocks the admin panel.
  const isModerator = computed(
    () => user.value?.roles.includes('moderator') || user.value?.roles.includes('admin'),
  )

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

  async function logout() {
    try {
      await axios.post('/api/v1/auth/logout', {}, { withCredentials: true })
    } catch {}
    accessToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
  }

  // A hard page load has the token but not the profile yet, and the router's
  // role checks read that profile — so the guard waits on this one request
  // instead of bouncing an admin who just typed /classroom/admin.
  let session: Promise<void> | null = null
  function ensureSession(): Promise<void> {
    if (!accessToken.value || user.value) return Promise.resolve()
    if (!session) {
      session = fetchMe().catch(() => logout()).finally(() => { session = null })
    }
    return session
  }

  // Restore session on page reload
  ensureSession()

  return { accessToken, user, isLoggedIn, isTeacher, isModerator, isAdmin, login, refresh, fetchMe, logout, ensureSession }
})
