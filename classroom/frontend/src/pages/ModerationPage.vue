<template>
  <div class="mod-page">
    <h1>Kiểm duyệt nội dung chia sẻ</h1>
    <p class="intro">
      Mọi link công khai tới file cá nhân đang còn hiệu lực, sắp theo lượt xem.
      Gỡ một link sẽ thu hồi quyền truy cập của link đó ngay; file vẫn nằm trong
      tài khoản của người gửi.
    </p>

    <div v-if="loading" class="muted">Đang tải…</div>
    <div v-else-if="error" class="alert-error">{{ error }}</div>
    <div v-else-if="!items.length" class="empty">Không có link chia sẻ nào đang hoạt động.</div>

    <div v-else>
      <p class="meta">Tổng: {{ items.length }} link</p>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Tệp</th>
              <th>Người chia sẻ</th>
              <th>Link</th>
              <th>Lượt xem</th>
              <th>Hiệu lực tới</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in items" :key="s.id">
              <td>{{ s.file_name }}</td>
              <td>
                <div>{{ s.owner_name || '—' }}</div>
                <div class="email">{{ s.owner_email }}</div>
              </td>
              <td class="token-cell">/shared/{{ s.share_token }}</td>
              <td>{{ s.view_count }}</td>
              <td>{{ s.expires_at ? fmt(s.expires_at) : 'Không hết hạn' }}</td>
              <td class="actions">
                <a class="btn-sm" :href="`/shared/${s.share_token}`" target="_blank">Mở</a>
                <button class="btn-sm danger" :disabled="busy === s.id" @click="takeDown(s)">
                  {{ busy === s.id ? 'Đang gỡ…' : 'Gỡ link' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '@/api/client'

interface SharedLink {
  id: string
  share_token: string
  file_name: string
  owner_id: string
  owner_name: string | null
  owner_email: string
  view_count: number
  created_at: string
  expires_at: string | null
}

const items = ref<SharedLink[]>([])
const loading = ref(true)
const error = ref('')
const busy = ref('')

function fmt(iso: string) {
  try {
    return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return ''
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<SharedLink[]>('/moderation/shares')
    items.value = data
  } catch {
    error.value = 'Không tải được danh sách liên kết chia sẻ.'
  } finally {
    loading.value = false
  }
}

async function takeDown(s: SharedLink) {
  const ok = window.confirm(
    `Gỡ link chia sẻ “${s.file_name}” của ${s.owner_name || s.owner_email}?\n` +
    'Người chia sẻ vẫn giữ tệp trong tài khoản của họ.',
  )
  if (!ok) return
  busy.value = s.id
  try {
    await api.delete(`/moderation/shares/${s.id}`)
    items.value = items.value.filter((x) => x.id !== s.id)
  } catch {
    error.value = 'Không gỡ được link, vui lòng thử lại.'
  } finally {
    busy.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
h1 { color: var(--amber-800); margin-bottom: 0.5rem; }
.intro { max-width: 70ch; font-size: 0.9rem; color: var(--color-text-muted); margin-bottom: 1.5rem; }
.meta { font-size: 0.85rem; color: var(--color-text-muted); }
.muted { color: var(--color-text-muted); }
.empty { padding: 2rem; color: var(--color-text-muted); }
.table-wrap { overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px var(--color-card-shadow); }
.table th, .table td { padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--amber-100); font-size: 0.875rem; vertical-align: middle; }
.table th { background: var(--amber-50); font-weight: 700; color: var(--amber-800); }
.table tr:last-child td { border-bottom: none; }
.email { font-size: 0.78rem; color: var(--color-text-muted); }
.token-cell { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.78rem; color: var(--color-text-muted); }
.actions { display: flex; gap: 0.4rem; }
.btn-sm {
  padding: 0.25rem 0.6rem; font-size: 0.8rem; border: 1px solid var(--amber-300);
  background: var(--amber-50); color: var(--amber-800); border-radius: 5px;
  cursor: pointer; font-weight: 600; text-decoration: none; white-space: nowrap;
}
.btn-sm:hover { background: var(--amber-100); }
.btn-sm.danger { background: #FEF2F2; color: #991B1B; border-color: #FECACA; }
.btn-sm.danger:hover { background: #FEE2E2; }
.btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.alert-error {
  background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA;
  border-radius: 6px; padding: 0.55rem 0.9rem; font-size: 0.875rem; margin-bottom: 0.75rem;
}
</style>
