<template>
  <div>
    <RouterLink :to="`/classes/${classId}/assignments/${assignmentId}`" class="back">← Quay lại bài tập</RouterLink>
    <div class="page-header">
      <h1>Nộp bài</h1>
      <span v-if="collabRole === 'writer'" class="badge badge-writer">✏️ Writer</span>
      <span v-else-if="collabRole === 'observer'" class="badge badge-observer">👁 Observer (xem)</span>
    </div>
    <p class="hint">
      <template v-if="collabRole === 'observer'">
        Bạn đang xem bài làm của nhóm. Chỉ Writer mới có thể chỉnh sửa.
      </template>
      <template v-else>
        Mở Jamovi bên dưới, làm việc, sau đó nhấn <strong>Nộp bài</strong>.
      </template>
    </p>

    <div v-if="sessionError" class="error">{{ sessionError }}</div>
    <div v-if="embedUrl" class="jamovi-wrapper">
      <iframe
        :src="embedUrl"
        class="jamovi-frame"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
      />
    </div>
    <div v-else-if="loadingSession" class="loading">Đang khởi động phiên Jamovi…</div>

    <div v-if="collabRole !== 'observer'" class="actions">
      <button :disabled="submitting || !embedUrl" @click="submit">
        {{ submitting ? 'Đang nộp…' : 'Nộp bài' }}
      </button>
    </div>
    <p v-if="submitSuccess" class="success">Nộp bài thành công!</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'

const route = useRoute()
const classId = route.params.classId as string
const assignmentId = route.params.assignmentId as string

const sessionToken = ref<string | null>(null)
const sessionPath = ref<string | null>(null)
const embedUrl = ref<string | null>(null)
const collabRole = ref<string>('writer')
const sessionError = ref('')
const loadingSession = ref(true)
const submitting = ref(false)
const submitSuccess = ref(false)

onMounted(async () => {
  loadingSession.value = true
  try {
    const { data } = await api.post('/sessions/token', { assignment_id: assignmentId })
    sessionToken.value = data.session_token
    sessionPath.value = data.session_path
    collabRole.value = data.collab_role ?? 'writer'
    // Use the full embed_url returned by the API (includes collab_token for Jamovi)
    embedUrl.value = data.embed_url
  } catch (e: any) {
    sessionError.value = e?.response?.data?.detail ?? 'Không thể khởi động phiên Jamovi'
  } finally { loadingSession.value = false }
})

onUnmounted(async () => {
  if (sessionToken.value) {
    try { await api.delete('/sessions/token', { data: { session_token: sessionToken.value } }) }
    catch {}
  }
})

async function submit() {
  if (!sessionToken.value || !sessionPath.value) return
  submitting.value = true
  submitSuccess.value = false
  try {
    // Take snapshot first
    await api.post('/sessions/snapshot', { session_token: sessionToken.value })
    // Then submit
    await api.post(`/assignments/${assignmentId}/submissions`, {
      session_path: sessionPath.value,
      notes: '',
    })
    submitSuccess.value = true
  } catch (e: any) {
    sessionError.value = e?.response?.data?.detail ?? 'Nộp bài thất bại'
  } finally { submitting.value = false }
}
</script>

<style scoped>
.back { color: #666; text-decoration: none; font-size: 0.9rem; }
.page-header { display: flex; align-items: center; gap: 0.75rem; margin: 0.5rem 0 0.3rem; }
h1 { margin: 0; }
.badge { padding: 0.25rem 0.65rem; border-radius: 12px; font-size: 0.82rem; font-weight: 700; }
.badge-writer { background: #27ae60; color: #fff; }
.badge-observer { background: #e67e22; color: #fff; }
.hint { color: #666; font-size: 0.9rem; margin-bottom: 1rem; }
.jamovi-wrapper { border: 1px solid #ddd; border-radius: 4px; overflow: hidden; margin-bottom: 1rem; }
.jamovi-frame { width: 100%; height: 70vh; border: none; }
.loading { color: #888; padding: 2rem 0; text-align: center; }
.actions { display: flex; gap: 1rem; margin-top: 1rem; }
button { padding: 0.6rem 1.5rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.success { color: green; font-weight: 600; margin-top: 0.5rem; }
.error { color: red; margin-bottom: 1rem; }
</style>

