<template>
  <div class="assignment-page">
    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="assignment">

      <RouterLink :to="`/classes/${classId}`" class="back-link">← Quay lại lớp</RouterLink>
      <div class="title-row">
        <h1>{{ assignment.title }}</h1>
        <button v-if="auth.isTeacher" class="btn-secondary" @click="showEditAssignment = true">✏️ Sửa bài tập</button>
      </div>
      <p class="desc">{{ assignment.description }}</p>
      <div class="meta-row">
        <span>Hạn nộp: <strong>{{ assignment.deadline ? fmtDate(assignment.deadline) : '—' }}</strong></span>
        <span>Loại: <strong>{{ typeLabel(assignment.assignment_type) }}</strong></span>
        <span v-if="assignment.max_score">Điểm tối đa: <strong>{{ assignment.max_score }}</strong></span>
        <span v-if="assignment.group_size > 1">Nhóm tối đa: <strong>{{ assignment.group_size }} người</strong></span>
      </div>

      <AssignmentEditModal :class-id="classId" :assignment="assignment"
                           v-model:show="showEditAssignment" @saved="assignment = $event" />

      <!-- ════ TEACHER VIEW ════════════════════════════════════════ -->
      <GradingConfigEditor v-if="auth.isTeacher"
                           :class-id="classId" :assignment-id="assignmentId"
                           :answer-key="assignment.answer_key" :grading-config="assignment.grading_config" />

      <div v-if="auth.isTeacher" class="section">
        <h2 class="section-title">Bài nộp của học viên</h2>
        <div v-if="loadingSubmissions" class="loading">Đang tải bài nộp…</div>
        <div v-else-if="!submissions.length" class="empty">Chưa có học viên nào nộp bài.</div>
        <table v-else class="sub-table">
          <thead>
            <tr>
              <th>Học viên</th>
              <th>Ngày nộp</th>
              <th>File</th>
              <th>Điểm</th>
              <th>Nhận xét</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in submissions" :key="s.id">
              <td class="td-name">{{ s.student_name || s.student_id.slice(0, 8) }}</td>
              <td class="td-date">{{ fmtDate(s.submitted_at) }}</td>
              <td class="td-file">
                <a v-if="s.file_path" href="#" class="file-link"
                   @click.prevent="saveFile(`/submissions/${s.id}/download`, `${s.student_name || s.id.slice(0, 8)}.omv`)">⬇ Tải về</a>
                <span v-else class="muted">—</span>
              </td>
              <td class="td-score">
                <input type="number" class="score-input" v-model.number="gradeMap[s.id].score"
                       :min="0" :max="assignment.max_score" placeholder="—" />
              </td>
              <td class="td-feedback">
                <input type="text" class="feedback-input" v-model="gradeMap[s.id].feedback"
                       placeholder="Nhận xét…" />
              </td>
              <td class="td-action">
                <button class="btn-sm" @click="openEvidence(s.id)">Xem bài</button>
                <button class="btn-grade" :disabled="gradeMap[s.id].saving" @click="saveGrade(s.id)">
                  {{ gradeMap[s.id].saving ? '…' : gradeMap[s.id].saved ? '✓' : 'Lưu' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ════ STUDENT VIEW ═══════════════════════════════════════ -->
      <template v-if="!auth.isTeacher">

        <!-- Group management -->
        <div v-if="assignment.group_size > 1 && assignment.assignment_type !== 'exam'" class="section">
          <div class="section-header">
            <h3>Nhóm làm bài</h3>
          </div>
          <div v-if="myGroup" class="group-box">
            <p><strong>Nhóm:</strong> {{ myGroup.group_name || `Nhóm ${myGroup.id.slice(0,6)}` }}</p>
            <p><strong>Vai trò:</strong>
              <span :class="myGroup.leader_id === currentUserId ? 'badge-writer' : 'badge-observer'">
                {{ myGroup.leader_id === currentUserId ? 'Writer (chỉnh sửa)' : 'Observer (xem)' }}
              </span>
            </p>
            <div class="member-list">
              <div v-for="m in myGroup.members" :key="m.user_id" class="member-row">
                <span>{{ m.full_name || m.user_id }}</span>
                <button v-if="myGroup.leader_id === currentUserId && m.user_id !== currentUserId"
                        class="btn-sm secondary" @click="transferLeader(m.user_id)">Chuyển quyền Writer</button>
              </div>
            </div>
          </div>
          <div v-else>
            <div class="group-create">
              <input v-model="newGroupName" placeholder="Tên nhóm (tuỳ chọn)" class="form-input sm" />
              <button class="btn-sm" @click="createGroup">+ Tạo nhóm mới</button>
            </div>
            <div v-if="groups.length" class="group-join-list">
              <p style="margin:0.5rem 0 0.3rem;font-weight:600;">Hoặc tham gia nhóm có sẵn:</p>
              <div v-for="g in groups" :key="g.id" class="group-join-row">
                <span>{{ g.group_name || `Nhóm ${g.id.slice(0,6)}` }}</span>
                <button class="btn-sm" @click="joinGroup(g.id)">Tham gia</button>
              </div>
            </div>
            <p v-if="groupError" class="error">{{ groupError }}</p>
          </div>
        </div>

        <!-- Class files -->
        <div v-if="classFiles.length" class="section">
          <h3>Tệp của lớp</h3>
          <div v-for="f in classFiles" :key="f.id" class="file-row">
            <span>{{ f.filename }}</span>
            <a href="#" class="link"
               @click.prevent="saveFile(`/classes/${classId}/files/${f.id}/download`, f.file_name)">Tải xuống</a>
          </div>
        </div>

        <!-- My submissions -->
        <div class="section">
          <div class="section-header">
            <h3>Bài nộp của tôi</h3>
            <div class="header-actions">
              <RouterLink
                v-if="!isPastDeadline"
                :to="`/classes/${classId}/assignments/${assignmentId}/submit`"
                class="btn-primary work-link"
              >📊 Làm bài trong HeyStat</RouterLink>
              <button v-if="canSubmit" class="btn-primary" @click="openSubmitModal">
                {{ mySubmissions.length ? 'Nộp lại' : 'Nộp bài' }}
              </button>
              <span v-else-if="isPastDeadline" class="badge-closed">Đã hết hạn</span>
            </div>
          </div>
          <div v-if="mySubmissions.length === 0" class="empty">Chưa có bài nộp.</div>
          <div v-for="s in mySubmissions" :key="s.id" class="sub-block">
            <div class="sub-row">
              <span>{{ fmtDate(s.submitted_at) }}</span>
              <span :class="`status-${s.status}`">{{ statusLabel(s.status) }}</span>
              <span v-if="s.is_final" class="final-tag">✓ Bài cuối</span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- ══ Teacher: submission evidence ═══════════════════════════ -->
    <div v-if="showEvidence" class="modal-overlay" @click.self="showEvidence = false">
      <div class="modal wide">
        <h2>Bài nộp</h2>
        <div v-if="evidenceLoading" class="loading">Đang tải…</div>
        <SubmissionEvidence v-else-if="evidence" :submission="evidence" />
        <div class="modal-actions">
          <button class="btn-secondary" @click="showEvidence = false">Đóng</button>
        </div>
      </div>
    </div>

    <!-- ══ Submit from "Tệp của tôi" Modal ══════════════════════ -->
    <div v-if="showSubmitModal" class="modal-overlay" @click.self="showSubmitModal = false">
      <div class="modal">
        <h2>Nộp bài</h2>
        <p class="modal-hint">Chọn file từ <strong>Tệp của tôi</strong> để nộp bài tập này.</p>

        <div v-if="loadingMyFiles" class="loading">Đang tải danh sách tệp…</div>
        <div v-else-if="!myFiles.length" class="empty-files">
          <p>📂 Bạn chưa có file nào trong <strong>Tệp của tôi</strong>.</p>
          <p>Hãy mở HeyStat, làm bài và nhấn <strong>💾 Lưu vào Tệp của tôi</strong> trong thanh công cụ, hoặc vào
             <RouterLink to="/files" class="link">Tệp của tôi</RouterLink> để tải file lên.</p>
          <RouterLink to="/files" class="btn-primary" style="text-decoration:none;margin-top:0.75rem;display:inline-block">Đến Tệp của tôi →</RouterLink>
        </div>
        <div v-else>
          <div v-for="f in myFiles" :key="f.id"
               class="file-option"
               :class="{ selected: selectedFileId === f.id }"
               @click="selectedFileId = f.id">
            <span class="file-icon">📄</span>
            <div class="file-info">
              <span class="file-name">{{ f.file_name }}</span>
              <span class="file-size">{{ formatSize(f.file_size) }} · {{ fmtDate(f.created_at) }}</span>
            </div>
            <span v-if="selectedFileId === f.id" class="check">✓</span>
          </div>
          <p v-if="submitError" class="error">{{ submitError }}</p>
          <div class="modal-actions">
            <button class="btn-secondary" @click="showSubmitModal = false">Huỷ</button>
            <button class="btn-primary" :disabled="!selectedFileId || submitting" @click="doSubmit">
              {{ submitting ? 'Đang nộp…' : 'Nộp bài' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'
import GradingConfigEditor from '@/components/GradingConfigEditor.vue'
import AssignmentEditModal from '@/components/AssignmentEditModal.vue'
import SubmissionEvidence from '@/components/SubmissionEvidence.vue'

const route = useRoute()
const classId = route.params.classId as string
const assignmentId = route.params.assignmentId as string
const auth = useAuthStore()

const loading = ref(true)
const assignment = ref<any>(null)
const showEditAssignment = ref(false)
const classFiles = ref<any[]>([])
const mySubmissions = ref<any[]>([])
const groups = ref<any[]>([])
const myGroup = ref<any>(null)
const newGroupName = ref('')
const groupError = ref('')

// Teacher
const submissions = ref<any[]>([])
const loadingSubmissions = ref(false)
const gradeMap = reactive<Record<string, { score: number|null, feedback: string, saving: boolean, saved: boolean }>>({})

// Teacher: submission evidence modal
const showEvidence = ref(false)
const evidence = ref<any>(null)
const evidenceLoading = ref(false)

// Student submit modal
const showSubmitModal = ref(false)
const myFiles = ref<any[]>([])
const loadingMyFiles = ref(false)
const selectedFileId = ref<string|null>(null)
const submitting = ref(false)
const submitError = ref('')

const currentUserId = computed(() => auth.user?.id ?? '')

const isPastDeadline = computed(() =>
  assignment.value?.deadline && new Date(assignment.value.deadline) < new Date()
)

const canSubmit = computed(() => {
  if (!assignment.value || isPastDeadline.value) return false
  if (!assignment.value.allow_resubmit && mySubmissions.value.length > 0) return false
  if (assignment.value.group_size > 1 && assignment.value.assignment_type !== 'exam' && !myGroup.value) return false
  return true
})

function fmtDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function typeLabel(t: string) {
  return { homework: 'Bài tập về nhà', project: 'Đồ án', exam: 'Kiểm tra' }[t] ?? t
}

function statusLabel(s: string) {
  return { submitted: 'Đã nộp', graded: 'Đã chấm', draft: 'Nháp' }[s] ?? s
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// The API only accepts a Bearer header, so a plain <a href> download would 401
async function saveFile(url: string, name: string) {
  const resp = await api.get(url, { responseType: 'blob' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(resp.data as Blob)
  link.download = name
  link.click()
  URL.revokeObjectURL(link.href)
}

// ── Teacher: load all submissions ──────────────────────────────
async function loadAllSubmissions() {
  loadingSubmissions.value = true
  try {
    const { data } = await api.get(`/assignments/${assignmentId}/submissions`)
    submissions.value = data
    data.forEach((s: any) => {
      gradeMap[s.id] = { score: s.score ?? null, feedback: s.feedback ?? '', saving: false, saved: false }
    })
  } finally { loadingSubmissions.value = false }
}

async function saveGrade(submissionId: string) {
  const g = gradeMap[submissionId]
  if (g.score === null || g.score === undefined) return
  g.saving = true; g.saved = false
  try {
    await api.post(`/assignments/${assignmentId}/submissions/${submissionId}/grade`, {
      score: g.score,
      feedback: g.feedback || null,
    })
    g.saved = true
    setTimeout(() => { g.saved = false }, 3000)
  } finally { g.saving = false }
}

async function openEvidence(submissionId: string) {
  showEvidence.value = true
  evidenceLoading.value = true
  evidence.value = null
  try {
    const { data } = await api.get(`/assignments/${assignmentId}/submissions/${submissionId}`)
    evidence.value = data
  } finally { evidenceLoading.value = false }
}

// ── Student: submit modal ──────────────────────────────────────
async function openSubmitModal() {
  showSubmitModal.value = true
  selectedFileId.value = null
  submitError.value = ''
  loadingMyFiles.value = true
  try {
    const { data } = await api.get('/files')
    myFiles.value = data
  } finally { loadingMyFiles.value = false }
}

async function doSubmit() {
  if (!selectedFileId.value) return
  submitting.value = true
  submitError.value = ''
  try {
    await api.post(`/assignments/${assignmentId}/submissions/from_file`, {
      user_file_id: selectedFileId.value,
    })
    showSubmitModal.value = false
    const { data } = await api.get(`/assignments/${assignmentId}/submissions/my`)
    mySubmissions.value = data
  } catch (e: any) {
    const d = e?.response?.data?.detail
    submitError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi nộp bài'
  } finally { submitting.value = false }
}

// ── Groups ─────────────────────────────────────────────────────
async function loadGroups() {
  if (!assignment.value || assignment.value.group_size <= 1 || assignment.value.assignment_type === 'exam') return
  try {
    const { data } = await api.get(`/classes/${classId}/assignments/${assignmentId}/groups`)
    groups.value = data
    myGroup.value = data.find((g: any) => g.members?.some((m: any) => m.user_id === currentUserId.value)) || null
  } catch {}
}

async function createGroup() {
  groupError.value = ''
  try {
    await api.post(`/classes/${classId}/assignments/${assignmentId}/groups`, { group_name: newGroupName.value || null })
    await loadGroups(); newGroupName.value = ''
  } catch (e: any) { groupError.value = e?.response?.data?.detail ?? 'Không thể tạo nhóm' }
}

async function joinGroup(groupId: string) {
  groupError.value = ''
  try {
    await api.post(`/classes/${classId}/assignments/${assignmentId}/groups/join`, { group_id: groupId })
    await loadGroups()
  } catch (e: any) { groupError.value = e?.response?.data?.detail ?? 'Không thể tham gia nhóm' }
}

async function transferLeader(userId: string) {
  if (!myGroup.value || !confirm('Chuyển quyền Writer cho thành viên này?')) return
  try {
    await api.patch(`/classes/${classId}/assignments/${assignmentId}/groups/${myGroup.value.id}/leader`, { new_leader_id: userId })
    await loadGroups()
  } catch (e: any) { groupError.value = e?.response?.data?.detail ?? 'Không thể chuyển quyền' }
}

onMounted(async () => {
  loading.value = true
  try {
    const [aRes, fRes] = await Promise.all([
      api.get(`/classes/${classId}/assignments/${assignmentId}`),
      api.get(`/classes/${classId}/files`),
    ])
    assignment.value = aRes.data
    classFiles.value = fRes.data
    if (auth.isTeacher) {
      await loadAllSubmissions()
    } else {
      const { data } = await api.get(`/assignments/${assignmentId}/submissions/my`)
      mySubmissions.value = data
      await loadGroups()
    }
  } finally { loading.value = false }
})
</script>

<style scoped>
.assignment-page {}
.loading { color: var(--color-text-muted); padding: 1rem 0; }
.back-link { color: var(--amber-700); text-decoration: none; font-size: 0.875rem; font-weight: 600; }
.back-link:hover { text-decoration: underline; }
h1 { margin: 0.5rem 0 0.25rem; color: var(--amber-800); }
.title-row { display: flex; align-items: center; gap: 0.75rem; }
.title-row h1 { flex: 1; }
.desc { color: var(--color-text-muted); margin-bottom: 1rem; line-height: 1.6; }
.meta-row { display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.875rem; color: var(--color-text-muted); margin-bottom: 1.75rem; }
.meta-row strong { color: var(--amber-800); }
.section { margin-bottom: 1.75rem; }
.section-title { color: var(--amber-800); font-size: 1.05rem; font-weight: 700; margin: 0 0 1rem; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.section-header h3 { margin: 0; color: var(--amber-800); }
.empty { color: var(--color-text-muted); padding: 0.5rem 0; font-size: 0.9rem; }
.muted { color: var(--color-text-muted); }

/* Teacher submissions table */
.sub-table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px var(--color-card-shadow); font-size: 0.875rem; }
.sub-table th { background: var(--amber-50); color: var(--amber-800); font-weight: 700; padding: 0.6rem 0.8rem; text-align: left; border-bottom: 2px solid var(--amber-200); }
.sub-table td { padding: 0.55rem 0.8rem; border-bottom: 1px solid var(--amber-100); vertical-align: middle; }
.sub-table tr:last-child td { border-bottom: none; }
.td-name { font-weight: 600; min-width: 120px; }
.td-date { color: var(--color-text-muted); white-space: nowrap; }
.file-link { color: var(--amber-700); text-decoration: none; font-weight: 600; }
.file-link:hover { text-decoration: underline; }
.score-input { width: 64px; padding: 0.3rem 0.4rem; border: 1px solid var(--amber-300); border-radius: 5px; font-size: 0.875rem; text-align: center; }
.feedback-input { width: 200px; padding: 0.3rem 0.5rem; border: 1px solid var(--amber-300); border-radius: 5px; font-size: 0.85rem; }
.score-input:focus, .feedback-input:focus { outline: none; border-color: var(--amber-500); }
.btn-grade { padding: 0.28rem 0.7rem; background: var(--color-primary); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 0.8rem; font-weight: 600; min-width: 44px; }
.btn-grade:hover { background: var(--color-primary-hover); }
.btn-grade:disabled { opacity: 0.6; cursor: not-allowed; }

/* Student submission rows */
.header-actions { display: flex; gap: 0.5rem; align-items: center; }
.work-link { text-decoration: none; }
.sub-block { border-bottom: 1px solid var(--amber-100); }
.sub-row { display: flex; gap: 0.75rem; align-items: center; padding: 0.6rem 0; font-size: 0.875rem; flex-wrap: wrap; }
.status-submitted { color: #d97706; font-weight: 600; }
.status-graded { color: #059669; font-weight: 600; }
.final-tag { color: #059669; font-weight: 700; font-size: 0.8rem; }
.badge-closed { background: #FEE2E2; color: #991B1B; padding: 0.2rem 0.6rem; border-radius: 8px; font-size: 0.8rem; font-weight: 600; }

/* Buttons */
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.45rem 1rem; border-radius: 7px; cursor: pointer; font-size: 0.875rem; font-weight: 600; display: inline-flex; align-items: center; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); padding: 0.45rem 1rem; border-radius: 7px; cursor: pointer; font-size: 0.875rem; font-weight: 600; }
.btn-sm { padding: 0.28rem 0.7rem; font-size: 0.8rem; border: 1px solid var(--amber-300); background: var(--amber-50); color: var(--amber-800); border-radius: 5px; cursor: pointer; font-weight: 600; }
.btn-sm.secondary { background: var(--amber-100); }
.link { color: var(--amber-700); text-decoration: none; font-size: 0.875rem; }
.link:hover { text-decoration: underline; }

/* File rows (class files) */
.file-row { display: flex; align-items: center; gap: 1rem; padding: 0.4rem 0; border-bottom: 1px solid var(--amber-100); font-size: 0.875rem; }

/* Group styles */
.group-box { background: var(--amber-50); border-radius: 8px; padding: 1rem; border: 1px solid var(--amber-200); }
.group-box p { margin: 0.3rem 0; font-size: 0.9rem; }
.member-list { margin-top: 0.5rem; }
.member-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0; font-size: 0.88rem; }
.group-create { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.form-input.sm { flex: 1; padding: 0.4rem 0.6rem; border: 1px solid var(--amber-300); border-radius: 6px; font-size: 0.875rem; }
.group-join-list { margin-top: 0.5rem; }
.group-join-row { display: flex; align-items: center; gap: 0.8rem; padding: 0.3rem 0; font-size: 0.9rem; }
.badge-writer { background: #D1FAE5; color: #065F46; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-observer { background: #FEF3C7; color: #92400E; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }

/* Submit modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 500; }
.modal { background: #fff; border-radius: 14px; padding: 2rem; width: 100%; max-width: 540px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); max-height: 80vh; overflow-y: auto; }
.modal.wide { max-width: 52rem; }
.modal h2 { color: var(--amber-800); margin: 0 0 0.5rem; font-size: 1.1rem; font-weight: 700; }
.modal-hint { color: var(--color-text-muted); font-size: 0.9rem; margin: 0 0 1.25rem; }
.empty-files { color: var(--color-text-muted); font-size: 0.9rem; line-height: 1.7; }
.empty-files p { margin: 0.25rem 0; }
.file-option { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 0.9rem; border: 1.5px solid var(--amber-200); border-radius: 8px; cursor: pointer; margin-bottom: 0.5rem; transition: border-color 0.15s, background 0.15s; }
.file-option:hover { border-color: var(--amber-400); background: var(--amber-50); }
.file-option.selected { border-color: var(--amber-500); background: var(--amber-50); }
.file-icon { font-size: 1.4rem; }
.file-info { flex: 1; }
.file-name { display: block; font-weight: 600; color: var(--amber-800); font-size: 0.9rem; }
.file-size { display: block; font-size: 0.78rem; color: var(--color-text-muted); }
.check { color: var(--amber-600); font-weight: 700; font-size: 1.1rem; }
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem; }
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.4rem 0.6rem; border-radius: 6px; margin: 0.75rem 0 0; }
</style>
