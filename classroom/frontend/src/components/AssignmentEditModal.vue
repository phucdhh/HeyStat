<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal">
      <h2>Sửa bài tập</h2>
      <div class="field">
        <label>Tiêu đề <span class="req">*</span></label>
        <input class="form-input" v-model="form.title" />
      </div>
      <div class="field">
        <label>Mô tả <span class="req">*</span></label>
        <textarea class="form-input" v-model="form.description" rows="3" />
      </div>
      <div class="field-row">
        <div class="field">
          <label>Hạn nộp <span class="req">*</span></label>
          <input class="form-input" type="datetime-local" v-model="form.deadline" />
        </div>
        <div class="field">
          <label>Điểm tối đa</label>
          <input class="form-input" type="number" v-model.number="form.max_score" min="0" max="100" />
        </div>
      </div>
      <div class="field">
        <label>Loại bài tập</label>
        <select class="form-input" v-model="form.assignment_type">
          <option value="homework">Bài tập về nhà</option>
          <option value="project">Đồ án / Dự án</option>
          <option value="exam">Kiểm tra</option>
        </select>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="modal-actions">
        <button class="btn-secondary" @click="close">Huỷ</button>
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Đang lưu…' : 'Lưu thay đổi' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import api from '@/api/client'

const props = defineProps<{ classId: string; assignment: any; show: boolean }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void; (e: 'saved', a: any): void }>()

const form = reactive({ title: '', description: '', deadline: '', max_score: 10, assignment_type: 'homework' })
const saving = ref(false)
const error = ref('')

function isoToLocal(iso: string) {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

watch(() => props.show, (v) => {
  if (!v || !props.assignment) return
  const a = props.assignment
  Object.assign(form, {
    title: a.title,
    description: a.description,
    deadline: isoToLocal(a.deadline),
    max_score: a.max_score,
    assignment_type: a.assignment_type || 'homework',
  })
  error.value = ''
})

function close() { emit('update:show', false) }

async function save() {
  error.value = ''
  if (!form.title.trim()) { error.value = 'Vui lòng nhập tiêu đề'; return }
  if (!form.description.trim()) { error.value = 'Vui lòng nhập mô tả'; return }
  if (!form.deadline) { error.value = 'Vui lòng chọn hạn nộp'; return }
  saving.value = true
  try {
    const { data } = await api.patch(`/classes/${props.classId}/assignments/${props.assignment.id}`, {
      title: form.title,
      description: form.description,
      deadline: new Date(form.deadline).toISOString(),
      max_score: form.max_score,
      assignment_type: form.assignment_type,
    })
    emit('saved', data)
    close()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    error.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi lưu'
  } finally { saving.value = false }
}
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
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem; }
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.4rem 0.6rem; border-radius: 6px; margin: 0 0 0.75rem; }
</style>
