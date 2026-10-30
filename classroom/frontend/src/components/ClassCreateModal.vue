<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal">
      <h2>Tạo lớp mới</h2>

      <div class="field">
        <label>Tên lớp <span class="req">*</span></label>
        <input class="form-input" v-model="form.title" placeholder="Ví dụ: Thống kê K1 2025"
               @keyup.enter="createClass" ref="titleRef" />
      </div>
      <div class="field">
        <label>Mô tả</label>
        <textarea class="form-input" v-model="form.description" rows="2"
                  placeholder="Mô tả ngắn về lớp học…" />
      </div>
      <div class="field-row">
        <div class="field">
          <label>Ngày bắt đầu <span class="req">*</span></label>
          <input class="form-input" type="datetime-local" v-model="form.starts_at" />
        </div>
        <div class="field">
          <label>Ngày kết thúc <span class="req">*</span></label>
          <input class="form-input" type="datetime-local" v-model="form.ends_at" />
        </div>
      </div>
      <div class="field">
        <label>Số học viên tối đa</label>
        <input class="form-input" type="number" v-model.number="form.max_students" min="1" max="500" />
      </div>

      <p v-if="createError" class="error">{{ createError }}</p>

      <div v-if="!createdKey" class="modal-actions">
        <button class="btn-secondary" @click="close">Huỷ</button>
        <button class="btn-primary" :disabled="creating" @click="createClass">
          {{ creating ? 'Đang tạo…' : 'Tạo lớp' }}
        </button>
      </div>

      <!-- The enrollment key is only ever returned by the create call. -->
      <div v-else class="created">
        <p class="ok">Lớp <strong>{{ createdTitle }}</strong> đã sẵn sàng. Gửi mã này cho học viên:</p>
        <div class="key-display">{{ createdKey }}</div>
        <p class="hint">Sau khi đóng hộp thoại bạn không xem lại mã được nữa, nhưng có thể sinh mã mới ở trang quản lý lớp.</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="copyKey">{{ copied ? '✓ Đã chép' : '📋 Sao chép mã' }}</button>
          <button class="btn-primary" @click="close">Xong</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch, nextTick } from 'vue'
import api from '@/api/client'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'created', id: string): void }>()

const nowIso = () => new Date().toISOString().slice(0, 16)
const endIso = () => {
  const d = new Date(); d.setMonth(d.getMonth() + 3); return d.toISOString().slice(0, 16)
}

const titleRef = ref<HTMLInputElement | null>(null)
const creating = ref(false)
const createError = ref('')
const createdKey = ref('')
const createdTitle = ref('')
const copied = ref(false)
const form = reactive({ title: '', description: '', max_students: 50, starts_at: nowIso(), ends_at: endIso() })

watch(() => props.show, (open) => {
  if (!open) return
  createError.value = ''
  createdKey.value = ''
  createdTitle.value = ''
  copied.value = false
  nextTick(() => titleRef.value?.focus())
})

async function createClass() {
  createError.value = ''
  if (!form.title.trim()) { createError.value = 'Vui lòng nhập tên lớp'; return }
  if (!form.starts_at) { createError.value = 'Vui lòng chọn ngày bắt đầu'; return }
  if (!form.ends_at) { createError.value = 'Vui lòng chọn ngày kết thúc'; return }
  creating.value = true
  try {
    const { data } = await api.post('/classes', {
      title: form.title,
      description: form.description,
      max_students: form.max_students,
      starts_at: new Date(form.starts_at).toISOString(),
      ends_at: new Date(form.ends_at).toISOString(),
    })
    createdKey.value = data.enrollment_key ?? ''
    createdTitle.value = data.title
    Object.assign(form, { title: '', description: '', max_students: 50, starts_at: nowIso(), ends_at: endIso() })
    emit('created', data.id)
  } catch (e: any) {
    const d = e?.response?.data?.detail
    createError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi tạo lớp'
  } finally { creating.value = false }
}

async function copyKey() {
  try {
    await navigator.clipboard.writeText(createdKey.value)
    copied.value = true
  } catch {}
}

function close() { emit('close') }
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 500; }
.modal { background: #fff; border-radius: 14px; padding: 2rem; width: 100%; max-width: 520px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal h2 { color: var(--amber-800); margin: 0 0 1.5rem; font-size: 1.1rem; font-weight: 700; }
.field { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem; }
.field > label { font-size: 0.875rem; font-weight: 600; color: var(--amber-800); }
.field-row { display: flex; gap: 1rem; }
.field-row .field { flex: 1; }
.req { color: #DC2626; }
.form-input { width: 100%; padding: 0.45rem 0.65rem; border: 1px solid var(--amber-300); border-radius: 6px; font-size: 0.9rem; box-sizing: border-box; }
.form-input:focus { outline: none; border-color: var(--amber-500); }
textarea.form-input { resize: vertical; }
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem; }
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.4rem 0.6rem; border-radius: 6px; margin: 0; }
.hint { font-size: 0.8rem; color: var(--color-text-muted); margin: 0.5rem 0 0; }
.ok { font-size: 0.9rem; color: #065F46; margin: 0 0 0.75rem; }
.key-display { font-size: 1.6rem; font-weight: 800; letter-spacing: 0.2em; color: var(--amber-800); background: var(--amber-50); padding: 1rem; border-radius: 8px; border: 2px dashed var(--amber-300); font-family: monospace; text-align: center; }
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
</style>
