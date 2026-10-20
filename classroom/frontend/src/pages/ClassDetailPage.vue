<template>
  <div class="class-detail-page">
    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="cls">

      <div class="page-header">
        <RouterLink to="/classes" class="back-link">← Danh sách lớp</RouterLink>
        <div>
          <h1>{{ cls.title }}</h1>
          <p class="sub" v-if="cls.description">{{ cls.description }}</p>
        </div>
      </div>

      <div class="tabs">
        <button v-for="tab in tabs" :key="tab.key"
                :class="{ active: activeTab === tab.key }"
                @click="activeTab = tab.key">{{ tab.label }}</button>
      </div>

      <!-- ── Assignments tab ───────────────────────────── -->
      <div v-if="activeTab === 'assignments'">
        <div class="tab-toolbar" v-if="auth.isTeacher">
          <button class="btn-primary" @click="showCreateAssignment = true">+ Tạo bài tập</button>
        </div>
        <div v-if="!assignments.length" class="empty">Chưa có bài tập.</div>
        <div v-for="a in assignments" :key="a.id" class="list-item">
          <RouterLink :to="`/classes/${classId}/assignments/${a.id}`" class="item-title">{{ a.title }}</RouterLink>
          <span class="meta">Hạn nộp: {{ a.deadline ? fmtDate(a.deadline) : 'Không có' }}</span>
          <span class="score-tag">{{ a.max_score }} điểm</span>
          <button v-if="auth.isTeacher" class="btn-icon" @click="openEditAssignment(a)" title="Sửa">✏️</button>
        </div>
      </div>

      <!-- ── Lessons tab ───────────────────────────────── -->
      <div v-if="activeTab === 'lessons'">
        <div class="tab-toolbar" v-if="auth.isTeacher">
          <button class="btn-primary" @click="showCreateLesson = true">+ Tạo bài học</button>
        </div>
        <div v-if="!lessons.length" class="empty">Chưa có bài học.</div>
        <div v-for="l in lessons" :key="l.id" class="list-item">
          <RouterLink :to="`/classes/${classId}/lessons/${l.id}`" class="item-title">{{ l.title }}</RouterLink>
          <button v-if="auth.isTeacher" class="btn-icon" @click="openEditLesson(l)" title="Sửa">✏️</button>
        </div>
      </div>

      <!-- ── Quizzes tab ───────────────────────────────── -->
      <div v-if="activeTab === 'quizzes'">
        <div class="tab-toolbar" v-if="auth.isTeacher">
          <RouterLink :to="`/classes/${classId}/quizzes/new`" class="btn-primary" style="text-decoration:none">+ Tạo Quiz</RouterLink>
        </div>
        <div v-if="!quizzes.length" class="empty">Chưa có quiz.</div>
        <div v-for="q in quizzes" :key="q.id" class="list-item">
          <RouterLink :to="`/classes/${classId}/quizzes/${q.id}`" class="item-title">{{ q.title }}</RouterLink>
          <span class="meta">{{ q.question_count }} câu hỏi</span>
        </div>
      </div>

      <!-- ── Files tab ─────────────────────────────────── -->
      <div v-if="activeTab === 'files'">
        <div class="tab-toolbar" v-if="auth.isTeacher">
          <button class="btn-primary" :disabled="uploadingFile" @click="fileInputRef?.click()">
            {{ uploadingFile ? 'Đang tải lên…' : '+ Tải lên tệp' }}
          </button>
          <input ref="fileInputRef" type="file" style="display:none" @change="uploadFile" />
        </div>
        <div v-if="!files.length" class="empty">Chưa có tệp.</div>
        <div v-for="f in files" :key="f.id" class="list-item">
          <span class="item-title link" @click="openInJamovi(f.id, f.file_name)">{{ f.file_name }}</span>
          <span class="meta">{{ f.file_size ? (f.file_size / 1024).toFixed(1) + ' KB' : '' }}</span>
          <button class="btn-icon" @click="downloadFile(f.id, f.file_name)" title="Tải xuống">↓ Tải</button>
          <button v-if="auth.isTeacher" class="btn-icon" @click="deleteFile(f.id)" title="Xoá">🗑️</button>
        </div>
      </div>

      <!-- ── Members tab (teacher only) ───────────────── -->
      <div v-if="activeTab === 'members' && auth.isTeacher">
        <div v-if="!members.length" class="empty">Chưa có học viên.</div>
        <table v-else class="table">
          <thead><tr><th>Tên</th><th>Email</th><th>Ngày tham gia</th></tr></thead>
          <tbody>
            <tr v-for="m in members" :key="m.user_id">
              <td>{{ m.full_name || m.username }}</td>
              <td>{{ m.email }}</td>
              <td>{{ m.enrolled_at ? fmtDate(m.enrolled_at) : '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── Analytics tab (teacher only) ─────────────────── -->
      <div v-if="activeTab === 'analytics' && auth.isTeacher">
        <ClassAnalytics :class-id="classId" />
      </div>
    </div>

    <!-- ── Create Assignment Modal ──────────────────────── -->
    <div v-if="showCreateAssignment" class="modal-overlay" @click.self="showCreateAssignment = false">
      <div class="modal">
        <h2>Tạo bài tập mới</h2>
        <div class="field">
          <label>Tiêu đề <span class="req">*</span></label>
          <input class="form-input" v-model="newAssignment.title" placeholder="Bài tập chương 1…" />
        </div>
        <div class="field">
          <label>Mô tả <span class="req">*</span></label>
          <textarea class="form-input" v-model="newAssignment.description" rows="3" placeholder="Yêu cầu, hướng dẫn…" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>Hạn nộp <span class="req">*</span></label>
            <input class="form-input" type="datetime-local" v-model="newAssignment.deadline" />
          </div>
          <div class="field">
            <label>Điểm tối đa</label>
            <input class="form-input" type="number" v-model.number="newAssignment.max_score" min="0" max="100" />
          </div>
        </div>
        <div class="field">
          <label>Loại bài tập</label>
          <select class="form-input" v-model="newAssignment.assignment_type">
            <option value="homework">Bài tập về nhà</option>
            <option value="project">Đồ án / Dự án</option>
            <option value="exam">Kiểm tra</option>
          </select>
        </div>
        <p v-if="assignmentError" class="error">{{ assignmentError }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreateAssignment = false">Huỷ</button>
          <button class="btn-primary" :disabled="savingAssignment" @click="createAssignment">
            {{ savingAssignment ? 'Đang tạo…' : 'Tạo bài tập' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Create Lesson Modal ──────────────────────────── -->
    <div v-if="showCreateLesson" class="modal-overlay" @click.self="showCreateLesson = false">
      <div class="modal">
        <h2>Tạo bài học mới</h2>
        <div class="field">
          <label>Tiêu đề <span class="req">*</span></label>
          <input class="form-input" v-model="newLesson.title" placeholder="Bài 1: Giới thiệu…" />
        </div>
        <div class="field">
          <label>Nội dung (Markdown)</label>
          <textarea class="form-input" v-model="newLesson.content" rows="5"
                    placeholder="## Nội dung bài học..." />
        </div>
        <div class="field">
          <label>Thứ tự</label>
          <input class="form-input" type="number" v-model.number="newLesson.sort_order" min="0" />
        </div>
        <p v-if="lessonError" class="error">{{ lessonError }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreateLesson = false">Huỷ</button>
          <button class="btn-primary" :disabled="savingLesson" @click="createLesson">
            {{ savingLesson ? 'Đang tạo…' : 'Tạo bài học' }}
          </button>
        </div>
      </div>
    </div>
    <!-- ── Edit Assignment Modal ──────────────────────── -->
    <div v-if="showEditAssignment" class="modal-overlay" @click.self="showEditAssignment = false">
      <div class="modal">
        <h2>Sửa bài tập</h2>
        <div class="field">
          <label>Tiêu đề <span class="req">*</span></label>
          <input class="form-input" v-model="editAssignment.title" />
        </div>
        <div class="field">
          <label>Mô tả <span class="req">*</span></label>
          <textarea class="form-input" v-model="editAssignment.description" rows="3" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>Hạn nộp <span class="req">*</span></label>
            <input class="form-input" type="datetime-local" v-model="editAssignment.deadline" />
          </div>
          <div class="field">
            <label>Điểm tối đa</label>
            <input class="form-input" type="number" v-model.number="editAssignment.max_score" min="0" max="100" />
          </div>
        </div>
        <div class="field">
          <label>Loại bài tập</label>
          <select class="form-input" v-model="editAssignment.assignment_type">
            <option value="homework">Bài tập về nhà</option>
            <option value="project">Đồ án / Dự án</option>
            <option value="exam">Kiểm tra</option>
          </select>
        </div>
        <p v-if="editAssignmentError" class="error">{{ editAssignmentError }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showEditAssignment = false">Huỷ</button>
          <button class="btn-primary" :disabled="savingEditAssignment" @click="saveEditAssignment">
            {{ savingEditAssignment ? 'Đang lưu…' : 'Lưu thay đổi' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Edit Lesson Modal ─────────────────────────── -->
    <div v-if="showEditLesson" class="modal-overlay" @click.self="showEditLesson = false">
      <div class="modal">
        <h2>Sửa bài học</h2>
        <div class="field">
          <label>Tiêu đề <span class="req">*</span></label>
          <input class="form-input" v-model="editLesson.title" />
        </div>
        <div class="field">
          <label>Nội dung (Markdown)</label>
          <textarea class="form-input" v-model="editLesson.content" rows="6" />
        </div>
        <div class="field">
          <label>Thứ tự</label>
          <input class="form-input" type="number" v-model.number="editLesson.sort_order" min="0" />
        </div>
        <p v-if="editLessonError" class="error">{{ editLessonError }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showEditLesson = false">Huỷ</button>
          <button class="btn-primary" :disabled="savingEditLesson" @click="saveEditLesson">
            {{ savingEditLesson ? 'Đang lưu…' : 'Lưu thay đổi' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import ClassAnalytics from '@/components/ClassAnalytics.vue'

const route = useRoute()
const auth = useAuthStore()
const classId = route.params.classId as string

const loading = ref(true)
const cls = ref<any>(null)
const assignments = ref<any[]>([])
const lessons = ref<any[]>([])
const quizzes = ref<any[]>([])
const files = ref<any[]>([])
const members = ref<any[]>([])
const uploadingFile = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const activeTab = ref('assignments')

const tabs = computed(() => {
  const t = [
    { key: 'assignments', label: 'Bài tập' },
    { key: 'lessons', label: 'Bài học' },
    { key: 'quizzes', label: 'Quiz' },
    { key: 'files', label: 'Tệp' },
  ]
  if (auth.isTeacher) t.push({ key: 'members', label: 'Học viên' })
  if (auth.isTeacher) t.push({ key: 'analytics', label: 'Phân tích' })
  return t
})

// ── Assignment creation ─────────────────────────────
const showCreateAssignment = ref(false)
const savingAssignment = ref(false)
const assignmentError = ref('')
const defaultDeadline = () => { const d = new Date(); d.setDate(d.getDate() + 7); return d.toISOString().slice(0, 16) }
const newAssignment = reactive({ title: '', description: '', deadline: defaultDeadline(), max_score: 10, assignment_type: 'homework' })

async function createAssignment() {
  assignmentError.value = ''
  if (!newAssignment.title.trim()) { assignmentError.value = 'Vui lòng nhập tiêu đề'; return }
  if (!newAssignment.description.trim()) { assignmentError.value = 'Vui lòng nhập mô tả'; return }
  if (!newAssignment.deadline) { assignmentError.value = 'Vui lòng chọn hạn nộp'; return }
  savingAssignment.value = true
  try {
    await api.post(`/classes/${classId}/assignments`, {
      ...newAssignment,
      deadline: new Date(newAssignment.deadline).toISOString(),
    })
    showCreateAssignment.value = false
    Object.assign(newAssignment, { title: '', description: '', deadline: defaultDeadline(), max_score: 10, assignment_type: 'homework' })
    const { data } = await api.get(`/classes/${classId}/assignments`)
    assignments.value = data
  } catch (e: any) {
    const d = e?.response?.data?.detail
    assignmentError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi tạo bài tập'
  } finally { savingAssignment.value = false }
}

// ── Lesson creation ──────────────────────────────────
const showCreateLesson = ref(false)
const savingLesson = ref(false)
const lessonError = ref('')
const newLesson = reactive({ title: '', content: '', sort_order: 0 })

async function createLesson() {
  lessonError.value = ''
  if (!newLesson.title.trim()) { lessonError.value = 'Vui lòng nhập tiêu đề'; return }
  savingLesson.value = true
  try {
    await api.post(`/classes/${classId}/lessons`, { ...newLesson })
    showCreateLesson.value = false
    Object.assign(newLesson, { title: '', content: '', sort_order: 0 })
    const { data } = await api.get(`/classes/${classId}/lessons`)
    lessons.value = data
  } catch (e: any) {
    const d = e?.response?.data?.detail
    lessonError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi tạo bài học'
  } finally { savingLesson.value = false }
}

// ── Assignment edit ────────────────────────────
// (ISO → datetime-local conversion helper)
function isoToLocal(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
const showEditAssignment = ref(false)
const savingEditAssignment = ref(false)
const editAssignmentError = ref('')
const editAssignment = reactive({ id: '', title: '', description: '', deadline: '', max_score: 10, assignment_type: 'homework' })
function openEditAssignment(a: any) {
  Object.assign(editAssignment, { id: a.id, title: a.title, description: a.description, deadline: isoToLocal(a.deadline), max_score: a.max_score, assignment_type: a.assignment_type || 'homework' })
  editAssignmentError.value = ''
  showEditAssignment.value = true
}
async function saveEditAssignment() {
  editAssignmentError.value = ''
  if (!editAssignment.title.trim()) { editAssignmentError.value = 'Vui lòng nhập tiêu đề'; return }
  if (!editAssignment.description.trim()) { editAssignmentError.value = 'Vui lòng nhập mô tả'; return }
  if (!editAssignment.deadline) { editAssignmentError.value = 'Vui lòng chọn hạn nộp'; return }
  savingEditAssignment.value = true
  try {
    const updated = await api.patch(`/classes/${classId}/assignments/${editAssignment.id}`, {
      title: editAssignment.title,
      description: editAssignment.description,
      deadline: new Date(editAssignment.deadline).toISOString(),
      max_score: editAssignment.max_score,
      assignment_type: editAssignment.assignment_type,
    })
    const idx = assignments.value.findIndex(a => a.id === editAssignment.id)
    if (idx !== -1) assignments.value[idx] = updated.data
    showEditAssignment.value = false
  } catch (e: any) {
    const d = e?.response?.data?.detail
    editAssignmentError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi lưu'
  } finally { savingEditAssignment.value = false }
}

// ── Lesson edit ───────────────────────────────
const showEditLesson = ref(false)
const savingEditLesson = ref(false)
const editLessonError = ref('')
const editLesson = reactive({ id: '', title: '', content: '', sort_order: 0 })
function openEditLesson(l: any) {
  Object.assign(editLesson, { id: l.id, title: l.title, content: l.content || '', sort_order: l.sort_order })
  editLessonError.value = ''
  showEditLesson.value = true
}
async function saveEditLesson() {
  editLessonError.value = ''
  if (!editLesson.title.trim()) { editLessonError.value = 'Vui lòng nhập tiêu đề'; return }
  savingEditLesson.value = true
  try {
    const updated = await api.patch(`/classes/${classId}/lessons/${editLesson.id}`, {
      title: editLesson.title,
      content: editLesson.content,
      sort_order: editLesson.sort_order,
    })
    const idx = lessons.value.findIndex(l => l.id === editLesson.id)
    if (idx !== -1) lessons.value[idx] = updated.data
    showEditLesson.value = false
  } catch (e: any) {
    const d = e?.response?.data?.detail
    editLessonError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi lưu'
  } finally { savingEditLesson.value = false }
}

async function uploadFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingFile.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await api.post(`/classes/${classId}/files`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    files.value.push(res.data)
  } catch (e: any) {
    const d = e?.response?.data?.detail
    alert(Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi tải lên file')
  } finally {
    uploadingFile.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
}

async function openInJamovi(fileId: string, fileName: string) {
  try {
    const res = await api.post(`/classes/${classId}/files/${fileId}/open-url`)
    const token: string = res.data.token
    const name: string = res.data.filename ?? fileName
    const base = window.location.origin
    const fileUrl = encodeURIComponent(`${base}/api/v1/files/ot/${token}`)
    const title = encodeURIComponent(name)
    window.open(`${base}/#open?url=${fileUrl}&title=${title}`, '_blank')
  } catch {
    alert('Không thể mở file trong Jamovi')
  }
}

async function downloadFile(fileId: string, fileName: string) {
  try {
    const res = await api.get(`/classes/${classId}/files/${fileId}/download`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    alert('Lỗi khi tải file')
  }
}

async function deleteFile(fileId: string) {
  if (!confirm('Xoá tệp này?')) return
  try {
    await api.delete(`/classes/${classId}/files/${fileId}`)
    files.value = files.value.filter(f => f.id !== fileId)
  } catch (e: any) {
    const d = e?.response?.data?.detail
    alert(Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi xoá file')
  }
}

function fmtDate(iso: string) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(async () => {
  loading.value = true
  try {
    const [clsRes, assignRes, lessonRes, quizRes, fileRes] = await Promise.all([
      api.get(`/classes/${classId}`),
      api.get(`/classes/${classId}/assignments`),
      api.get(`/classes/${classId}/lessons`),
      api.get(`/classes/${classId}/quizzes`),
      api.get(`/classes/${classId}/files`),
    ])
    cls.value = clsRes.data
    assignments.value = assignRes.data
    lessons.value = lessonRes.data
    quizzes.value = quizRes.data
    files.value = fileRes.data
    if (auth.isTeacher) {
      const memberRes = await api.get(`/classes/${classId}/students`)
      members.value = memberRes.data
    }
  } finally { loading.value = false }
})
</script>

<style scoped>
.class-detail-page {}
.loading { color: var(--color-text-muted); padding: 2rem 0; }
.page-header { margin-bottom: 1.5rem; }
.back-link { font-size: 0.85rem; color: var(--amber-700); text-decoration: none; font-weight: 600; }
.back-link:hover { color: var(--amber-900); text-decoration: underline; }
.page-header h1 { margin: 0.4rem 0 0.25rem; color: var(--amber-800); }
.sub { color: var(--color-text-muted); margin: 0; font-size: 0.9rem; }
.tabs { display: flex; gap: 0.25rem; margin-bottom: 1.5rem; border-bottom: 2px solid var(--amber-200); }
.tabs button { padding: 0.5rem 1.1rem; border: none; background: transparent; cursor: pointer; font-size: 0.9rem; border-bottom: 3px solid transparent; margin-bottom: -2px; color: var(--color-text-muted); }
.tabs button:hover { color: var(--amber-700); }
.tabs button.active { border-bottom-color: var(--amber-600); font-weight: 700; color: var(--amber-800); }
.tab-toolbar { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; }
.list-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 0; border-bottom: 1px solid var(--amber-100); flex-wrap: wrap; }
.item-title { font-weight: 600; color: var(--amber-800); text-decoration: none; flex: 1; }
.item-title:hover { color: var(--amber-900); text-decoration: underline; }
.item-title.link { cursor: pointer; }
.meta { font-size: 0.8rem; color: var(--color-text-muted); }
.score-tag { font-size: 0.78rem; background: var(--amber-100); color: var(--amber-800); padding: 0.1rem 0.5rem; border-radius: 8px; font-weight: 600; }
.empty { color: var(--color-text-muted); padding: 1.5rem 0; font-size: 0.9rem; }
.table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px var(--color-card-shadow); }
.table th, .table td { padding: 0.6rem 0.9rem; text-align: left; border-bottom: 1px solid var(--amber-100); font-size: 0.875rem; }
.table th { background: var(--amber-50); font-weight: 700; color: var(--amber-800); }
.table tr:last-child td { border-bottom: none; }
/* Buttons */
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.45rem 1rem; border-radius: 7px; cursor: pointer; font-size: 0.875rem; font-weight: 600; display: inline-flex; align-items: center; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); padding: 0.45rem 1rem; border-radius: 7px; cursor: pointer; font-size: 0.875rem; font-weight: 600; }
/* Modal */
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
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.4rem 0.6rem; border-radius: 6px; margin: 0 0 0.75rem; }
.btn-icon { background: transparent; border: none; cursor: pointer; font-size: 0.95rem; padding: 0 0.25rem; opacity: 0.6; line-height: 1; }
.btn-icon:hover { opacity: 1; }
</style>
