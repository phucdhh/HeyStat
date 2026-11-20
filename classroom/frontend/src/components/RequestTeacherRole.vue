<template>
  <div v-if="!auth.isTeacher" class="panel">
    <h2>Bạn là giảng viên?</h2>

    <p v-if="loading" class="muted">Đang tải…</p>

    <template v-else-if="latest && latest.status === 'pending'">
      <p>
        Yêu cầu của bạn đã gửi và đang chờ Admin duyệt. Bạn sẽ nhận được thông báo
        trong ứng dụng khi có kết quả.
      </p>
      <p class="meta">{{ sentLabel }}</p>
      <button class="btn-secondary" :disabled="checking" @click="recheck">
        {{ checking ? 'Đang kiểm tra…' : 'Kiểm tra lại quyền' }}
      </button>
    </template>

    <template v-else-if="latest && latest.status === 'rejected'">
      <p class="warn">
        Yêu cầu gần nhất chưa được duyệt.
        <span v-if="latest.review_note">Lý do: {{ latest.review_note }}</span>
      </p>
      <button class="btn-secondary" @click="openForm">Gửi yêu cầu khác</button>
    </template>

    <template v-else>
      <p class="muted">
        Tài khoản của bạn đang ở mức Người dùng: thực hành Jamovi, vào lớp bằng mã lớp và nộp bài
        được ngay, nhưng chưa tạo được lớp học. Gửi yêu cầu để Admin mở quyền tạo lớp.
      </p>
      <button class="btn-primary" @click="openForm">Xin mở quyền tạo lớp</button>
      <a class="help-link" href="/help" target="_blank">Xem hướng dẫn dành cho giảng viên</a>
    </template>

    <div v-if="showForm" class="modal-backdrop" @click.self="closeForm">
      <div class="modal">
        <h3>Gửi yêu cầu mở quyền tạo lớp</h3>
        <form @submit.prevent="submit">
          <div class="field">
            <label>Đơn vị công tác</label>
            <input v-model.trim="form.institution" class="form-input" placeholder="VD: Khoa Y tế công cộng, Trường ĐH Y Dược" />
          </div>
          <div class="field">
            <label>Lý do <span class="required">*</span></label>
            <textarea
              v-model.trim="form.reason"
              class="form-input"
              rows="4"
              minlength="10"
              required
              placeholder="VD: Tôi phụ trách học phần Thống kê Y học cho lớp XTSK26 và cần giao bài thực hành jamovi."
            />
            <small class="muted">Ít nhất 10 ký tự — Admin dựa vào thông tin này để duyệt.</small>
          </div>
          <div v-if="error" class="alert-error">{{ error }}</div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="closeForm">Huỷ</button>
            <button type="submit" class="btn-primary" :disabled="sending">
              {{ sending ? 'Đang gửi…' : 'Gửi yêu cầu' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

interface TeacherRequest {
  id: string
  status: string
  institution: string | null
  reason: string | null
  review_note: string | null
  created_at: string
  reviewed_at: string | null
}

const auth = useAuthStore()
const latest = ref<TeacherRequest | null>(null)
const loading = ref(true)
const checking = ref(false)
const sending = ref(false)
const showForm = ref(false)
const error = ref('')
const form = ref({ institution: '', reason: '' })

const sentLabel = computed(() => {
  const at = latest.value?.created_at
  if (!at) return ''
  try {
    return `Gửi ngày ${new Date(at).toLocaleString('vi-VN', { dateStyle: 'medium', timeStyle: 'short' })}.`
  } catch {
    return ''
  }
})

async function load() {
  loading.value = true
  try {
    const { data } = await api.get<TeacherRequest[]>('/teacher-requests/mine')
    latest.value = data.length ? data[0] : null
  } catch {
    latest.value = null
  } finally {
    loading.value = false
  }
}

function openForm() {
  error.value = ''
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  error.value = ''
}

async function submit() {
  sending.value = true
  error.value = ''
  try {
    const { data } = await api.post<TeacherRequest>('/teacher-requests', {
      institution: form.value.institution || null,
      reason: form.value.reason,
    })
    latest.value = data
    form.value = { institution: '', reason: '' }
    showForm.value = false
  } catch (err: any) {
    const d = err.response?.data?.detail
    error.value = typeof d === 'string' ? d : 'Không gửi được yêu cầu, vui lòng thử lại'
  } finally {
    sending.value = false
  }
}

// An approval changes the account's roles, which the app only learns from /auth/me.
async function recheck() {
  checking.value = true
  try {
    await auth.fetchMe()
    await load()
  } finally {
    checking.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.panel {
  background: #fff;
  border: 1.5px solid var(--amber-200);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-top: 2rem;
  max-width: 640px;
}
h2 { font-size: 1.05rem; color: var(--amber-800); margin: 0 0 0.5rem; }
h3 { font-size: 1rem; color: var(--amber-800); margin: 0 0 1rem; }
p { font-size: 0.9rem; color: var(--color-text); margin: 0 0 0.75rem; }
.meta { color: var(--color-text-muted); font-size: 0.8rem; }
.warn { color: #991B1B; }
.muted { color: var(--color-text-muted); }
.help-link { display: inline-block; margin-left: 0.75rem; font-size: 0.85rem; color: var(--amber-700); }
.btn-primary, .btn-secondary {
  border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600;
  padding: 0.5rem 1.1rem; border: 1px solid transparent;
}
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border-color: var(--amber-300); }
.form-input {
  width: 100%; padding: 0.45rem 0.6rem; border: 1px solid var(--amber-300);
  border-radius: 6px; font-size: 0.9rem; font-family: inherit;
}
.form-input:focus { outline: none; border-color: var(--amber-500); }
.field { display: flex; flex-direction: column; gap: 0.3rem; margin-bottom: 1rem; }
.field > label { font-size: 0.85rem; font-weight: 600; color: var(--amber-800); }
.required { color: #DC2626; }
.alert-error {
  background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA;
  border-radius: 6px; padding: 0.5rem 0.8rem; font-size: 0.85rem; margin-bottom: 0.75rem;
}
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 500; padding: 1rem;
}
.modal {
  background: #fff; border-radius: 14px; padding: 1.75rem;
  width: 100%; max-width: 480px; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1rem; }
</style>
