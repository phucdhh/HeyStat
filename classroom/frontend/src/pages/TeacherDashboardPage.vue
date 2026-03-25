<template>
  <div class="teacher-page">
    <h1>Quản lý lớp học</h1>

    <div class="tabs">
      <button v-for="tab in ['classes', 'progress']" :key="tab"
              :class="{ active: activeTab === tab }"
              @click="activeTab = tab">
        {{ tab === 'classes' ? 'Lớp của tôi' : 'Tiến độ học viên' }}
      </button>
    </div>

    <!-- My classes tab -->
    <div v-if="activeTab === 'classes'">
      <div class="page-header">
        <button class="btn-primary" @click="showCreate = true">+ Tạo lớp mới</button>
      </div>
      <div v-if="loading" class="loading">Đang tải…</div>
      <div v-else-if="!classes.length" class="empty">Chưa có lớp nào.</div>
      <div v-else class="grid">
        <div v-for="cls in classes" :key="cls.id" class="class-card">
          <div class="cls-title">{{ cls.title }}</div>
          <div class="cls-dates">
            <span>{{ fmtDate(cls.starts_at) }}</span> – <span>{{ fmtDate(cls.ends_at) }}</span>
          </div>
          <div class="cls-meta">
            <RouterLink :to="`/classes/${cls.id}`">Xem lớp →</RouterLink>
          </div>
          <div class="cls-actions">
            <button class="btn-sm" @click="exportGrades(cls.id)">Xuất bảng điểm</button>
            <button class="btn-sm secondary" @click="copyKey(cls)">Sao chép mã lớp</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Progress tab -->
    <div v-if="activeTab === 'progress'">
      <div class="select-wrap">
        <label>Chọn lớp:</label>
        <select class="form-input" v-model="selectedClass" @change="loadProgress">
          <option v-for="cls in classes" :key="cls.id" :value="cls.id">{{ cls.title }}</option>
        </select>
      </div>
      <div v-if="progressLoading" class="loading">Đang tải…</div>
      <div v-else-if="progress">
        <div v-for="s in progress.students" :key="s.user_id" class="progress-row">
          <span class="student-name">{{ s.full_name || s.username }}</span>
          <div class="progress-bars">
            <div v-for="sub in s.submissions" :key="sub.assignment_id"
                 class="sub-dot" :class="sub.status" :title="sub.assignment_title"></div>
          </div>
          <span class="avg">TB: {{ s.average_score != null ? s.average_score.toFixed(1) : '—' }}</span>
        </div>
      </div>
    </div>

    <!-- Create class modal -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal">
        <h2>Tạo lớp mới</h2>
        <div class="field">
          <label>Tên lớp <span class="req">*</span></label>
          <input class="form-input" v-model="newClass.title" placeholder="Ví dụ: Thống kê K1 2025" />
        </div>
        <div class="field">
          <label>Mô tả</label>
          <textarea class="form-input" v-model="newClass.description" rows="2" placeholder="Mô tả ngắn về lớp học…" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>Ngày bắt đầu <span class="req">*</span></label>
            <input class="form-input" type="datetime-local" v-model="newClass.starts_at" />
          </div>
          <div class="field">
            <label>Ngày kết thúc <span class="req">*</span></label>
            <input class="form-input" type="datetime-local" v-model="newClass.ends_at" />
          </div>
        </div>
        <div class="field">
          <label>Số học viên tối đa</label>
          <input class="form-input" v-model.number="newClass.max_students" type="number" min="1" max="500" />
        </div>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreate = false">Huỷ</button>
          <button class="btn-primary" :disabled="creating" @click="createClass">
            {{ creating ? 'Đang tạo…' : 'Tạo lớp' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="copiedMsg" class="toast">{{ copiedMsg }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import api from '@/api/client'

const classes = ref<any[]>([])
const loading = ref(true)
const activeTab = ref('classes')
const selectedClass = ref<string | null>(null)
const progress = ref<any>(null)
const progressLoading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const nowIso = () => new Date().toISOString().slice(0, 16)
const endIso = () => {
  const d = new Date(); d.setMonth(d.getMonth() + 3); return d.toISOString().slice(0, 16)
}
const newClass = reactive({ title: '', description: '', max_students: 50, starts_at: nowIso(), ends_at: endIso() })
const createError = ref('')
const copiedMsg = ref('')

function fmtDate(iso: string) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/classes')
    classes.value = data
    if (data.length) selectedClass.value = data[0].id
  } finally { loading.value = false }
}

async function loadProgress() {
  if (!selectedClass.value) return
  progressLoading.value = true
  try {
    const { data } = await api.get(`/classes/${selectedClass.value}/progress`)
    progress.value = data
  } finally { progressLoading.value = false }
}

async function createClass() {
  createError.value = ''
  if (!newClass.title.trim()) { createError.value = 'Vui lòng nhập tên lớp'; return }
  if (!newClass.starts_at) { createError.value = 'Vui lòng chọn ngày bắt đầu'; return }
  if (!newClass.ends_at) { createError.value = 'Vui lòng chọn ngày kết thúc'; return }
  creating.value = true
  try {
    await api.post('/classes', {
      title: newClass.title,
      description: newClass.description,
      max_students: newClass.max_students,
      starts_at: new Date(newClass.starts_at).toISOString(),
      ends_at: new Date(newClass.ends_at).toISOString(),
    })
    showCreate.value = false
    Object.assign(newClass, { title: '', description: '', max_students: 50, starts_at: nowIso(), ends_at: endIso() })
    await load()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    createError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi tạo lớp'
  } finally { creating.value = false }
}

async function exportGrades(classId: string) {
  window.open(`/api/v1/classes/${classId}/grades/export`, '_blank')
}

async function copyKey(cls: any) {
  try {
    const { data } = await api.get(`/classes/${cls.id}`)
    await navigator.clipboard.writeText(data.enrollment_key_display || cls.id)
    copiedMsg.value = 'Đã sao chép!'
    setTimeout(() => (copiedMsg.value = ''), 2000)
  } catch {}
}

onMounted(load)
</script>

<style scoped>
.teacher-page {}
h1 { color: var(--amber-800); margin-bottom: 1rem; }
.tabs { display: flex; gap: 0.25rem; margin-bottom: 1.5rem; border-bottom: 2px solid var(--amber-200); }
.tabs button { padding: 0.5rem 1.25rem; border: none; background: transparent; cursor: pointer; font-size: 0.95rem; border-bottom: 3px solid transparent; margin-bottom: -2px; color: var(--color-text-muted); }
.tabs button:hover { color: var(--amber-700); }
.tabs button.active { border-bottom-color: var(--amber-600); font-weight: 700; color: var(--amber-800); }
.page-header { margin-bottom: 1rem; }
.loading, .empty { padding: 2rem; color: var(--color-text-muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 1rem; }
.class-card { background: #fff; border: 1.5px solid var(--amber-200); border-radius: 10px; padding: 1.1rem; box-shadow: 0 1px 4px var(--color-card-shadow); }
.cls-title { font-weight: 700; font-size: 1rem; color: var(--amber-900); margin-bottom: 0.3rem; }
.cls-dates { font-size: 0.8rem; color: var(--color-text-muted); margin-bottom: 0.5rem; }
.cls-meta { font-size: 0.85rem; margin-bottom: 0.7rem; }
.cls-meta a { color: var(--amber-700); text-decoration: none; font-weight: 600; }
.cls-meta a:hover { color: var(--amber-900); text-decoration: underline; }
.cls-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.btn-sm { padding: 0.28rem 0.7rem; font-size: 0.8rem; border: 1px solid var(--amber-300); background: var(--amber-50); color: var(--amber-800); border-radius: 5px; cursor: pointer; font-weight: 600; }
.btn-sm:hover { background: var(--amber-100); }
.btn-sm.secondary { background: var(--amber-100); color: var(--amber-900); }
.select-wrap { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; }
.select-wrap label { font-weight: 600; color: var(--amber-800); }
.progress-row { display: flex; align-items: center; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid var(--amber-100); }
.student-name { width: 180px; font-size: 0.9rem; }
.progress-bars { display: flex; flex-wrap: wrap; gap: 4px; flex: 1; }
.sub-dot { width: 14px; height: 14px; border-radius: 50%; }
.sub-dot.graded { background: #27ae60; }
.sub-dot.submitted { background: #e67e22; }
.sub-dot.missing { background: #e0e0e0; }
.avg { width: 80px; text-align: right; font-size: 0.85rem; color: var(--color-text-muted); }
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
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
.error { color: #DC2626; font-size: 0.85rem; margin: 0.5rem 0; }
.toast { position: fixed; bottom: 2rem; right: 2rem; background: var(--amber-800); color: #fff; padding: 0.65rem 1.25rem; border-radius: 8px; font-size: 0.9rem; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
</style>
