<template>
  <div>
    <div v-if="loading">Đang tải…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="fileData">
      <h2>{{ fileData.original_name }}</h2>
      <p class="meta">Được chia sẻ bởi {{ fileData.owner_username }} · {{ (fileData.size_bytes / 1024).toFixed(1) }} KB</p>
      <p class="hint">Đây là chế độ xem chỉ đọc. Mọi thay đổi sẽ không được lưu.</p>
      <div class="jamovi-wrapper">
        <iframe
          :src="jamoviUrl"
          class="jamovi-frame"
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'

const route = useRoute()
const token = route.params.token as string

const loading = ref(true)
const error = ref('')
const fileData = ref<any>(null)

const jamoviUrl = computed(() =>
  fileData.value ? `/?open=${encodeURIComponent(fileData.value.tmp_path)}&readonly=1` : ''
)

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get(`/shared/${token}`)
    fileData.value = data
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Link không hợp lệ hoặc đã hết hạn'
  } finally { loading.value = false }
})
</script>

<style scoped>
h2 { margin-bottom: 0.3rem; }
.meta { color: #666; font-size: 0.9rem; margin-bottom: 0.5rem; }
.hint { background: #fff3cd; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem; margin-bottom: 1rem; }
.jamovi-wrapper { border: 1px solid #ddd; border-radius: 4px; overflow: hidden; }
.jamovi-frame { width: 100%; height: 80vh; border: none; }
.error { color: red; padding: 2rem 0; text-align: center; font-size: 1.1rem; }
</style>
