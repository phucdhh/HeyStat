<template>
  <div>
    <h1>Tệp của tôi</h1>

    <!-- Upload -->
    <div class="upload-box">
      <input ref="fileInput" type="file" accept=".csv,.xlsx,.xls,.sav,.sas7bdat,.ods,.omv" hidden @change="onFileChosen" />
      <button @click="(fileInput as HTMLInputElement).click()">+ Tải tệp lên</button>
      <span v-if="uploading" class="hint">Đang tải…</span>
      <span v-if="uploadError" class="error">{{ uploadError }}</span>
    </div>

    <!-- File list -->
    <div v-if="loading">Đang tải…</div>
    <div v-else-if="files.length === 0" class="empty">Chưa có tệp nào.</div>
    <table v-else class="table">
      <thead><tr><th>Tên tệp</th><th>Kích thước</th><th>Ngày tải</th><th>Thao tác</th></tr></thead>
      <tbody>
        <tr v-for="f in files" :key="f.id">
          <td>{{ f.original_name }}</td>
          <td>{{ (f.size_bytes / 1024).toFixed(1) }} KB</td>
          <td>{{ new Date(f.created_at).toLocaleString('vi-VN') }}</td>
          <td class="actions-cell">
            <button class="small" @click="openInJamovi(f)">Mở Jamovi</button>
            <button class="small secondary" @click="openShareDialog(f)">Chia sẻ</button>
            <button class="small danger" @click="deleteFile(f.id)">Xoá</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- ── Share Dialog ── -->
    <div v-if="shareDialog.open" class="modal-overlay" @click.self="closeShareDialog">
      <div class="modal">
        <h2>Chia sẻ tệp</h2>
        <p class="file-name">{{ shareDialog.file?.original_name }}</p>

        <!-- If no link exists yet -->
        <template v-if="!shareDialog.link">
          <label>Thời hạn link:</label>
          <select v-model="shareDialog.expiry">
            <option value="1">1 giờ</option>
            <option value="24">1 ngày</option>
            <option value="168">7 ngày</option>
            <option value="720">30 ngày</option>
            <option value="">Không giới hạn</option>
          </select>
          <div class="modal-actions">
            <button @click="createShareLink">Tạo link</button>
            <button class="secondary" @click="closeShareDialog">Huỷ</button>
          </div>
          <p v-if="shareDialog.error" class="error">{{ shareDialog.error }}</p>
        </template>

        <!-- After link created -->
        <template v-else>
          <label>Link chia sẻ (chỉ đọc):</label>
          <div class="link-row">
            <input :value="shareDialog.link" readonly ref="linkInputRef" class="link-input" />
            <button class="small" @click="copyLink">{{ copied ? 'Đã sao chép!' : 'Sao chép' }}</button>
          </div>
          <div class="modal-actions" style="margin-top:1rem">
            <button class="danger small" @click="revokeShareLink">Thu hồi link</button>
            <button class="secondary" @click="closeShareDialog">Đóng</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, nextTick } from 'vue'
import api from '@/api/client'

const files = ref<any[]>([])
const loading = ref(true)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadError = ref('')
const linkInputRef = ref<HTMLInputElement | null>(null)
const copied = ref(false)

const shareDialog = reactive({
  open: false,
  file: null as any,
  expiry: '24',   // hours
  link: '',
  error: '',
})

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/files')
    files.value = data
  } finally { loading.value = false }
}

async function onFileChosen(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length) return
  const file = input.files[0]
  input.value = ''
  uploadError.value = ''; uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    await api.post('/files', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    await load()
  } catch (err: any) {
    uploadError.value = err?.response?.data?.detail ?? 'Tải lên thất bại'
  } finally { uploading.value = false }
}

async function deleteFile(id: string) {
  if (!confirm('Xoá tệp này?')) return
  try {
    await api.delete(`/files/${id}`)
    await load()
  } catch {}
}

function openShareDialog(f: any) {
  shareDialog.file = f
  shareDialog.link = ''
  shareDialog.expiry = '24'
  shareDialog.error = ''
  shareDialog.open = true
}

function closeShareDialog() {
  shareDialog.open = false
}

async function createShareLink() {
  shareDialog.error = ''
  try {
    let expiresAt: string | null = null
    if (shareDialog.expiry) {
      const d = new Date()
      d.setHours(d.getHours() + parseInt(shareDialog.expiry))
      expiresAt = d.toISOString()
    }
    const { data } = await api.post(`/files/${shareDialog.file.id}/share`, { expires_at: expiresAt })
    shareDialog.link = `${window.location.origin}/classroom/shared/${data.token}`
  } catch (err: any) {
    shareDialog.error = err?.response?.data?.detail ?? 'Không thể tạo link'
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(shareDialog.link)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // Fallback: select the input
    linkInputRef.value?.select()
  }
}

async function revokeShareLink() {
  if (!confirm('Thu hồi link? Người đang xem sẽ không truy cập được nữa.')) return
  try {
    await api.delete(`/files/${shareDialog.file.id}/share`)
    shareDialog.link = ''
    shareDialog.open = false
  } catch (err: any) {
    shareDialog.error = err?.response?.data?.detail ?? 'Lỗi khi thu hồi'
  }
}

function openInJamovi(f: any) {
  window.open(`/?open=${encodeURIComponent(f.jamovi_path)}`, '_blank')
}

onMounted(load)
</script>

<style scoped>
h1 { margin-bottom: 1rem; }
.upload-box { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.5rem; }
button { padding: 0.5rem 1rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9rem; }
.table th { background: #f8f8f8; font-weight: 600; }
.actions-cell { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.small { padding: 0.3rem 0.6rem; font-size: 0.8rem; }
.secondary { background: #f0f0f0; color: #333; }
.danger { background: #e74c3c; }
.error { color: red; font-size: 0.85rem; }
.hint { color: #888; font-size: 0.9rem; }
.empty { color: #888; }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal {
  background: #fff; border-radius: 8px; padding: 1.5rem 2rem;
  min-width: 400px; max-width: 90vw; box-shadow: 0 8px 30px rgba(0,0,0,0.2);
}
.modal h2 { margin: 0 0 0.5rem; font-size: 1.1rem; }
.file-name { color: #555; margin: 0 0 1rem; font-size: 0.9rem; }
.modal label { display: block; margin-bottom: 0.3rem; font-weight: 600; font-size: 0.9rem; }
.modal select { width: 100%; padding: 0.4rem; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 1rem; }
.modal-actions { display: flex; gap: 0.5rem; }
.link-row { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.link-input { flex: 1; padding: 0.4rem; font-family: monospace; font-size: 0.8rem; border: 1px solid #cce3f5; border-radius: 4px; background: #f6fbff; }
</style>

