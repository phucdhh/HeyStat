import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

interface Notification {
  id: string
  message: string
  is_read: boolean
  created_at: string
}

export const useNotifStore = defineStore('notifications', () => {
  const items = ref<Notification[]>([])
  const unread = ref(0)

  async function fetch() {
    const { data } = await api.get('/notifications')
    items.value = data
    unread.value = data.filter((n: Notification) => !n.is_read).length
  }

  async function markRead(id: string) {
    await api.patch(`/notifications/${id}/read`)
    const n = items.value.find((x) => x.id === id)
    if (n && !n.is_read) {
      n.is_read = true
      unread.value = Math.max(0, unread.value - 1)
    }
  }

  async function markAllRead() {
    await api.post('/notifications/read-all')
    items.value.forEach((n) => (n.is_read = true))
    unread.value = 0
  }

  return { items, unread, fetch, markRead, markAllRead }
})
