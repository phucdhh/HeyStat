<template>
  <div>
    <div v-if="loading">Đang tải…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="fileData">
      <h2>{{ fileData.file_name }}</h2>
      <p class="meta">Được chia sẻ bởi {{ fileData.owner_username }} · {{ fileData.size_bytes != null ? (fileData.size_bytes / 1024).toFixed(1) + ' KB' : '—' }}</p>
      <p class="hint">Đây là chế độ xem chỉ đọc. Mọi thay đổi sẽ không được lưu.</p>
      <div v-if="jamoviUrl" class="jamovi-wrapper">
        <iframe
          :src="jamoviUrl"
          class="jamovi-frame"
          allow="clipboard-write; clipboard-read"
        />
      </div>
      <div v-else class="loading-jamovi">Đang mở file trong Jamovi…</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'

const route = useRoute()
const token = route.params.token as string

const loading = ref(true)
const error = ref('')
const fileData = ref<any>(null)
const jamoviUrl = ref('')

onMounted(async () => {
  loading.value = true
  try {
    // 1. Lấy metadata (file_name, owner_username, size_bytes)
    const { data } = await api.get(`/shared/${token}`)
    fileData.value = data

    // 2. Tải file blob qua endpoint public (không cần auth)
    const fileResp = await fetch(`/api/v1/shared/${token}/file`)
    if (!fileResp.ok) throw new Error(`Không thể tải file: HTTP ${fileResp.status}`)
    const blob = await fileResp.blob()

    // 3. POST lên Jamovi /open (cùng origin) để lấy URL session
    // credentials: 'include' đảm bảo cookie hs_shared_session được gửi kèm
    // để nginx auth_request cho phép request này đi qua
    const form = new FormData()
    form.append('file', blob, data.file_name)
    const openResp = await fetch('/open', { method: 'POST', body: form, credentials: 'include' })
    const text = await openResp.text()
    const lines = text.trim().split('\n')
    const result = JSON.parse(lines[lines.length - 1])
    if (result.status === 'OK' && result.url) {
      const url = result.url.startsWith('/') ? result.url : '/' + result.url
      jamoviUrl.value = url + '?readonly=1'
    } else {
      throw new Error(result.message || 'Jamovi không thể mở file')
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? 'Link không hợp lệ hoặc đã hết hạn'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
h2 { margin-bottom: 0.3rem; }
.meta { color: #666; font-size: 0.9rem; margin-bottom: 0.5rem; }
.hint { background: #fff3cd; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem; margin-bottom: 1rem; }
.jamovi-wrapper { border: 1px solid #ddd; border-radius: 4px; overflow: hidden; }
.jamovi-frame { width: 100%; height: 80vh; border: none; }
.loading-jamovi { padding: 3rem; text-align: center; color: #888; }
.error { color: red; padding: 2rem 0; text-align: center; font-size: 1.1rem; }
</style>
