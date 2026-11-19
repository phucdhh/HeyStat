import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

const BEAT_MS = 30000
const TAB_KEY = 'hs_presence_tab'

/** One id per browser tab, so a student who opens the same class twice is still
 * one person, and closing one tab does not wipe the other's claim. */
function tabId(): string {
  let id = sessionStorage.getItem(TAB_KEY)
  if (!id) {
    const raw = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`
    id = raw.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 64)
    sessionStorage.setItem(TAB_KEY, id)
  }
  return id
}

export const usePresenceStore = defineStore('presence', () => {
  const classId = ref('')
  const editing = ref(false)
  let timer: number | undefined
  let listening = false

  async function beat() {
    if (!classId.value) return
    try {
      await api.post('/presence/beat', {
        class_id: classId.value,
        tab_id: tabId(),
        editing: editing.value,
      })
    } catch {
      // Presence is advisory. A lost beat must never interrupt a student's work.
    }
  }

  function startTimer() {
    if (!timer) timer = window.setInterval(beat, BEAT_MS)
  }

  function stopTimer() {
    if (!timer) return
    clearInterval(timer)
    timer = undefined
  }

  function onVisibility() {
    if (document.visibilityState === 'visible') {
      if (!classId.value) return
      void beat()
      startTimer()
    } else {
      // A background tab is not "attending", but say so by going quiet rather than
      // by shouting offline: Safari may bring the tab back a second later.
      stopTimer()
    }
  }

  /** Leaving the seat is a beacon because the tab is on its way out and an axios
   * request would be killed with it; it cannot carry a header, hence the cookie
   * authentication on /presence/leave. */
  function announceExit() {
    if (!classId.value) return
    const tab = tabId()
    const url = `/api/v1/presence/leave?tab=${encodeURIComponent(tab)}`
    if (!navigator.sendBeacon?.(url)) {
      void api.post('/presence/leave', null, { params: { tab } }).catch(() => {})
    }
  }

  function enter(id: string) {
    if (!id || id === classId.value) return
    if (classId.value) exit()
    classId.value = id
    if (!listening) {
      document.addEventListener('visibilitychange', onVisibility)
      window.addEventListener('pagehide', exit)
      listening = true
    }
    void beat()
    startTimer()
  }

  function exit() {
    announceExit()
    classId.value = ''
    editing.value = false
    stopTimer()
  }

  async function setEditing(value: boolean) {
    if (editing.value === value) return
    editing.value = value
    // Report the editor opening straight away; the teacher is watching this count
    // during a practical session and 30 seconds of lag reads as a dead class.
    if (classId.value && document.visibilityState === 'visible') await beat()
  }

  function shutdown() {
    exit()
    if (!listening) return
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('pagehide', exit)
    listening = false
  }

  return { classId, editing, enter, exit, setEditing, shutdown, beat }
})
