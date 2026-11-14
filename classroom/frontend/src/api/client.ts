import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
})

let refreshing = false
let queue: Array<() => void> = []

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      if (!refreshing) {
        refreshing = true
        try {
          const auth = useAuthStore()
          await auth.refresh()
          queue.forEach((fn) => fn())
          queue = []
        } catch (refreshError: any) {
          // A timeout or 5xx means the server is overloaded, not that the
          // session ended. Logging out here caused a re-login storm while
          // jamovi was saturating the machine.
          const status = refreshError?.response?.status
          if (status === 401 || status === 403) {
            const auth = useAuthStore()
            auth.logout()
          }
          return Promise.reject(error)
        } finally {
          refreshing = false
        }
      } else {
        await new Promise<void>((resolve) => queue.push(resolve))
      }
      const auth = useAuthStore()
      original.headers.Authorization = `Bearer ${auth.accessToken}`
      return api(original)
    }
    return Promise.reject(error)
  },
)

export default api
