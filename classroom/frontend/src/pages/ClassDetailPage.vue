<template>
  <div class="class-detail-page">
    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="cls">

      <div class="page-header">
        <RouterLink to="/classes" class="back-link">← Danh sách lớp</RouterLink>
        <div>
          <h1>{{ cls.title }}</h1>
          <p class="sub" v-if="cls.description">{{ cls.description }}</p>
          <p class="sub" v-if="cls.teacher_name && cls.teacher_id !== auth.user?.id">👤 Giáo viên: {{ cls.teacher_name }}</p>
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
          <span class="kind-tag">{{ kindLabel(a) }}</span>
          <span v-if="a.answer_key?.questions?.length || a.grading_config?.checks?.length" class="chip auto">chấm tự động</span>
          <span v-if="a.file_id" class="meta">📊 có bộ dữ liệu</span>
          <span class="score-tag">{{ a.max_score }} điểm</span>
          <button v-if="auth.isTeacher" class="btn-icon" @click="openEditAssignment(a)" title="Sửa">✏️</button>
          <button v-if="auth.isTeacher" class="btn-icon" @click="deleteAssignment(a)" title="Xoá">🗑️</button>
        </div>
      </div>

      <!-- ── Lessons tab ───────────────────────────────── -->
      <div v-if="activeTab === 'lessons'">
        <div class="tab-toolbar" v-if="auth.isTeacher">
          <button class="btn-primary" @click="openCreateLesson">+ Tạo bài học</button>
        </div>
        <div v-if="!lessons.length" class="empty">Chưa có bài học.</div>
        <div v-for="(l, i) in lessons" :key="l.id" class="list-item">
          <span class="kind-tag">{{ typeOf(l.lesson_type).icon }} {{ typeOf(l.lesson_type).label }}</span>
          <RouterLink :to="`/classes/${classId}/lessons/${l.id}`" class="item-title">{{ l.title }}</RouterLink>
          <span v-if="auth.isTeacher && !l.is_published" class="chip wait">nháp</span>
          <span v-if="l.resource_count" class="meta">📎 {{ l.resource_count }} tài nguyên</span>
          <template v-if="auth.isTeacher">
            <button class="btn-icon" :disabled="i === 0" title="Lên trên" @click="moveLesson(i, -1)">↑</button>
            <button class="btn-icon" :disabled="i === lessons.length - 1" title="Xuống dưới" @click="moveLesson(i, 1)">↓</button>
            <button v-if="l.is_published" class="btn-icon pub" title="Ngừng công khai" @click="togglePublish(l)">🌐</button>
            <button v-else class="btn-icon draft" title="Công khai" @click="togglePublish(l)">🔒</button>
            <button class="btn-icon" title="Sửa" @click="openEditLesson(l)">✏️</button>
            <button class="btn-icon" title="Xoá" @click="deleteLesson(l)">🗑️</button>
          </template>
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
        <div class="tab-toolbar">
          <button class="btn-secondary" :disabled="exporting" @click="exportRoster">
            {{ exporting ? 'Đang xuất…' : '⬇ Xuất CSV' }}
          </button>
          <span class="meta">Bảng CSV gồm từng bài tập một cột, mở trực tiếp bằng Excel.</span>
        </div>
        <div v-if="!members.length" class="empty">Chưa có học viên.</div>
        <template v-else>
          <div class="roster-stats">
            <div class="rs"><span class="v">{{ roster.total }}</span><span class="l">học viên đang học</span></div>
            <div class="rs"><span class="v">{{ roster.submitted }}</span><span class="l">đã nộp ít nhất 1 bài</span></div>
            <div class="rs"><span class="v">{{ roster.atRisk }}</span><span class="l">chưa nộp bài nào</span></div>
            <div class="rs"><span class="v">{{ roster.awaiting }}</span><span class="l">bài chờ thầy/cô chấm</span></div>
            <div class="rs"><span class="v">{{ roster.average ?? '—' }}</span><span class="l">điểm trung bình lớp</span></div>
          </div>

          <table class="table roster">
            <thead>
              <tr>
                <th aria-label="Chi tiết"></th>
                <th>Học viên</th>
                <th>Tiến độ nộp bài</th>
                <th>Chấm điểm</th>
                <th>Điểm TB</th>
                <th>Hoạt động cuối</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="m in members" :key="m.id">
                <tr :class="{ 'row-atrisk': roster.isAtRisk(m) }">
                  <td class="cell-toggle">
                    <button class="toggle" :class="{ open: expanded[m.id] }"
                            :aria-expanded="!!expanded[m.id]"
                            :aria-label="expanded[m.id] ? 'Ẩn chi tiết' : 'Xem chi tiết'"
                            @click="toggleStudent(m.id)">{{ expanded[m.id] ? '▾' : '▸' }}</button>
                  </td>
                  <td>
                    <div class="who">
                      <strong>{{ m.full_name }}</strong>
                      <span class="muted">{{ m.email }}</span>
                      <span v-if="m.status !== 'active'" class="chip drop">đã rời lớp</span>
                    </div>
                  </td>
                  <td>
                    <div class="prog-line">
                      <span>{{ m.submitted }}/{{ m.assignments_total }}</span>
                      <span v-if="m.missing" class="chip miss">nợ {{ m.missing }}</span>
                    </div>
                    <div class="bar"><div class="fill" :style="{ width: donePct(m) + '%' }" /></div>
                  </td>
                  <td>
                    <div class="prog-line">
                      <span>{{ m.graded }} đã chấm</span>
                      <span v-if="m.awaiting_grade" class="chip wait">{{ m.awaiting_grade }} chờ</span>
                    </div>
                  </td>
                  <td>
                    <div class="prog-line">
                      <strong>{{ m.average_score ?? '—' }}</strong>
                      <span v-if="m.score_pct !== null" class="muted">{{ m.score_pct }}%</span>
                    </div>
                  </td>
                  <td class="muted">{{ m.last_activity ? fmtDate(m.last_activity) : 'chưa hoạt động' }}</td>
                </tr>
                <tr v-if="expanded[m.id]" class="detail-row">
                  <td></td>
                  <td colspan="5">
                    <div v-if="!m.progress.length" class="empty">Lớp chưa có bài tập.</div>
                    <div v-for="p in m.progress" :key="p.assignment_id" class="progress-row">
                      <span class="dot" :class="p.state"></span>
                      <span class="p-title">{{ p.title }}</span>
                      <span class="p-state">{{ stateLabels[p.state] }}</span>
                      <span class="muted">hạn {{ fmtDate(p.deadline) }}</span>
                      <span v-if="p.submitted_at" class="muted">nộp {{ fmtDate(p.submitted_at) }}</span>
                      <span v-else-if="p.synced_at" class="muted">kết quả đồng bộ {{ fmtDate(p.synced_at) }}</span>
                      <span v-if="p.score !== null" class="score-tag">{{ p.score }}/{{ p.max_score }}</span>
                      <span v-if="p.mistakes" class="chip miss">{{ p.mistakes }} lỗi</span>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </template>
      </div>

      <!-- ── Analytics tab (teacher only) ─────────────────── -->
      <div v-if="activeTab === 'analytics' && auth.isTeacher">
        <ClassAnalytics :class-id="classId" />
      </div>
    </div>

    <!-- ── Create Assignment ──────────────────────── -->
    <AssignmentCreateModal :class-id="classId" :files="files"
                           v-model:show="showCreateAssignment"
                           @created="onAssignmentCreated" @uploaded="onFileUploaded" />

    <!-- ── Lesson editor (create + edit) ────────────────── -->
    <LessonEditorModal :class-id="classId" :files="files" :lesson="editingLesson"
                       v-model:show="showLessonEditor" @saved="onLessonSaved" />

    <!-- ── Edit Assignment Modal ──────────────────────── -->
    <AssignmentEditModal :class-id="classId" :assignment="editAssignment"
                         v-model:show="showEditAssignment" @saved="onAssignmentSaved" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import ClassAnalytics from '@/components/ClassAnalytics.vue'
import AssignmentEditModal from '@/components/AssignmentEditModal.vue'
import AssignmentCreateModal from '@/components/AssignmentCreateModal.vue'
import LessonEditorModal from '@/components/LessonEditorModal.vue'
import { kindLabel } from '@/utils/assignmentTemplates'
import { lessonTypeOf as typeOf } from '@/utils/lessonTemplates'
import { downloadFile as downloadCsv } from '@/utils/download'
import { openClassFileInJamovi } from '@/utils/openInJamovi'

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
const activeTab = ref('lessons')

const tabs = computed(() => {
  const t = [
    { key: 'lessons', label: 'Bài học' },
    { key: 'assignments', label: 'Bài tập' },
    { key: 'quizzes', label: 'Quiz' },
    { key: 'files', label: 'Tệp' },
  ]
  if (auth.isTeacher) t.push({ key: 'members', label: 'Học viên' })
  if (auth.isTeacher) t.push({ key: 'analytics', label: 'Phân tích' })
  return t
})

// ── Members tab ─────────────────────────────────────
const stateLabels: Record<string, string> = {
  graded: 'đã chấm',
  submitted: 'đã nộp, chờ chấm',
  missing: 'chưa nộp – quá hạn',
  open: 'chưa tới hạn',
}
const expanded = ref<Record<string, boolean>>({})
function toggleStudent(id: string) { expanded.value[id] = !expanded.value[id] }
function donePct(m: any) {
  return m.assignments_total ? Math.round((m.submitted / m.assignments_total) * 100) : 0
}
function isAtRisk(m: any) {
  return m.status === 'active' && m.submitted === 0 && m.missing > 0
}
const roster = computed(() => {
  const active = members.value.filter(m => m.status === 'active')
  const scores = active.map(m => m.average_score).filter((s: any) => s !== null)
  return {
    total: active.length,
    submitted: active.filter(m => m.submitted > 0).length,
    atRisk: active.filter(isAtRisk).length,
    awaiting: active.reduce((n: number, m: any) => n + m.awaiting_grade, 0),
    average: scores.length ? (scores.reduce((a: number, b: number) => a + b, 0) / scores.length).toFixed(2) : null,
    isAtRisk,
  }
})

const exporting = ref(false)

/** One CSV per class, one column per assignment — the same rows the table shows. */
async function exportRoster() {
  exporting.value = true
  try {
    await downloadCsv(`/classes/${classId}/students/export`, `hoc_vien_${classId}.csv`)
  } catch {
    alert('Không xuất được CSV — hãy thử lại sau ít phút')
  } finally { exporting.value = false }
}

// ── Assignment creation ─────────────────────────────
const showCreateAssignment = ref(false)

function onAssignmentCreated(a: any) {
  assignments.value.unshift(a)
}
function onFileUploaded(f: any) {
  files.value.push({ ...f, created_at: new Date().toISOString() })
}

// ── Lessons ──────────────────────────────────────────
const showLessonEditor = ref(false)
const editingLesson = ref<any>(null)

async function reloadLessons() {
  const { data } = await api.get(`/classes/${classId}/lessons`)
  lessons.value = data
}

function openCreateLesson() {
  editingLesson.value = null
  showLessonEditor.value = true
}

function openEditLesson(l: any) {
  editingLesson.value = l
  showLessonEditor.value = true
}

function onLessonSaved(saved: any) {
  const idx = lessons.value.findIndex(l => l.id === saved.id)
  if (idx === -1) lessons.value.push(saved)
  else lessons.value[idx] = { ...lessons.value[idx], ...saved }
  lessons.value.sort((a, b) => a.sort_order - b.sort_order)
}

async function togglePublish(l: any) {
  await api.patch(`/classes/${classId}/lessons/${l.id}`, { is_published: !l.is_published })
  await reloadLessons()
}

async function moveLesson(i: number, dir: number) {
  const j = i + dir
  if (j < 0 || j >= lessons.value.length) return
  const order = lessons.value.map(l => l.id)
  ;[order[i], order[j]] = [order[j], order[i]]
  await api.patch(`/classes/${classId}/lessons/reorder`, { order })
  await reloadLessons()
}

// ── Assignment edit ────────────────────────────
const showEditAssignment = ref(false)
const editAssignment = ref<any>(null)
function openEditAssignment(a: any) {
  editAssignment.value = a
  showEditAssignment.value = true
}
function onAssignmentSaved(updated: any) {
  const idx = assignments.value.findIndex(a => a.id === updated.id)
  if (idx !== -1) assignments.value[idx] = updated
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
    await openClassFileInJamovi(classId, fileId, fileName)
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

async function deleteLesson(l: any) {
  if (!confirm(`Xoá bài học “${l.title}”?\n\nToàn bộ tài nguyên đính kèm cũng bị xoá.`)) return
  try {
    await api.delete(`/classes/${classId}/lessons/${l.id}`)
    await reloadLessons()
  } catch (e: any) {
    alert(e?.response?.data?.detail ?? 'Lỗi khi xoá bài học')
  }
}

// The server cascades to the submissions, so the only warning a teacher gets is
// this one — hence the count, fetched before asking rather than after deleting.
async function deleteAssignment(a: any) {
  let n = 0
  try {
    const { data } = await api.get(`/assignments/${a.id}/submissions`)
    n = data.length
  } catch { /* the plain warning still stops an accidental click */ }
  const warning = n
    ? `Xoá bài tập “${a.title}”?\n\n${n} bài nộp của học viên sẽ mất theo, không phục hồi được.`
    : `Xoá bài tập “${a.title}”?`
  if (!confirm(warning)) return
  try {
    await api.delete(`/classes/${classId}/assignments/${a.id}`)
    assignments.value = assignments.value.filter(x => x.id !== a.id)
  } catch (e: any) {
    alert(e?.response?.data?.detail ?? 'Lỗi khi xoá bài tập')
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
      members.value = memberRes.data.sort((a: any, b: any) => a.full_name.localeCompare(b.full_name, 'vi'))
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
/* Members tab */
.roster-stats { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-bottom: 1rem; }
.rs { background: #fff; border: 1px solid var(--amber-200); border-radius: 10px; padding: 0.5rem 0.9rem; box-shadow: 0 1px 4px var(--color-card-shadow); }
.rs .v { display: block; font-size: 1.15rem; font-weight: 700; color: var(--amber-800); }
.rs .l { font-size: 0.75rem; color: var(--color-text-muted); }
.roster td { vertical-align: middle; }
.row-atrisk td { background: #FEF2F2; }
.cell-toggle { width: 2rem; padding-right: 0 !important; }
.toggle { border: none; background: transparent; cursor: pointer; font-size: 1rem; line-height: 1; color: var(--amber-600); padding: 0.2rem 0.4rem; border-radius: 6px; }
.toggle:hover { background: var(--amber-100); color: var(--amber-900); }
.toggle.open { color: #DC2626; }
.who { display: flex; flex-direction: column; gap: 0.1rem; }
.muted { color: var(--color-text-muted); font-size: 0.78rem; }
.prog-line { display: flex; align-items: center; gap: 0.4rem; }
.bar { height: 5px; background: var(--amber-100); border-radius: 4px; margin-top: 0.3rem; min-width: 80px; overflow: hidden; }
.fill { height: 100%; background: var(--amber-500); border-radius: 4px; }
.chip { font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.45rem; border-radius: 8px; white-space: nowrap; }
.chip.miss { background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; }
.chip.wait { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); }
.chip.drop { background: #F3F4F6; color: #6B7280; }
.chip.auto { background: #E7F6EC; color: #166534; border: 1px solid #BBE5C7; }
.kind-tag { font-size: 0.72rem; font-weight: 700; color: var(--amber-700); background: var(--amber-100); border: 1px solid var(--amber-200); padding: 0.1rem 0.45rem; border-radius: 8px; white-space: nowrap; }
.detail-row td { background: var(--amber-50); padding-top: 0.4rem; padding-bottom: 0.5rem; }
.progress-row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; padding: 0.28rem 0; font-size: 0.82rem; }
.p-title { font-weight: 600; color: var(--amber-800); }
.p-state { color: var(--color-text-muted); font-size: 0.75rem; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
.dot.graded { background: #16A34A; }
.dot.submitted { background: var(--amber-500); }
.dot.missing { background: #DC2626; }
.dot.open { background: #D1D5DB; }
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
.btn-icon:disabled { opacity: 0.2; cursor: default; }
.btn-icon.pub, .btn-icon.draft { opacity: 1; border-radius: 6px; padding: 0.1rem 0.3rem; }
.btn-icon.pub { background: #E7F6EC; }
.btn-icon.draft { background: var(--amber-100); }
.check-row { display: flex; align-items: center; gap: 0.45rem; font-size: 0.875rem; color: var(--amber-800); margin-bottom: 1rem; }
</style>
