<template>
  <div class="submit-page" @keydown.esc="handleEscape">
    <header class="page-header">
      <div class="heading">
        <RouterLink :to="`/classes/${classId}/assignments/${assignmentId}`" class="back">← Bài tập</RouterLink>
        <h1 :title="assignment?.title">{{ assignment?.title ?? 'Nộp bài' }}</h1>
        <span v-if="session && collabRole === 'writer'" class="badge writer">Writer</span>
        <span v-else-if="collabRole === 'observer'" class="badge observer">Observer (xem)</span>
      </div>
      <div class="metadata">
        <span v-if="assignment?.deadline" class="deadline">Hạn: {{ fmt(assignment.deadline) }}</span>
        <RouterLink to="/help" class="helplink">Cách đọc kết quả</RouterLink>
      </div>
    </header>

    <div class="toolbar">
      <div v-if="!assignmentClosed && collabRole !== 'observer'" class="actions">
        <button class="secondary" :disabled="!canSync" @click="syncResults">
          {{ syncing ? 'Đang đồng bộ…' : 'Đồng bộ kết quả' }}
        </button>
        <button :disabled="!canSubmit" @click="submit">
          {{ submitting ? 'Đang nộp…' : 'Nộp bài' }}
        </button>
      </div>
      <p class="save-status" role="status">
        <template v-if="submitSuccess">Đã nộp bài. Phiên làm việc đã đóng băng.</template>
        <template v-else-if="collabRole === 'observer'">Chỉ trưởng nhóm (Writer) được lưu và nộp bài.</template>
        <template v-else-if="autoSaving">Đang tự lưu nháp…</template>
        <template v-else-if="savedAt">
          Đã lưu nháp lúc {{ savedAt.toLocaleTimeString('vi-VN') }}<span v-if="answersChanged"> · Đáp án có thay đổi chưa lưu</span>
        </template>
        <template v-else-if="canWrite">Tự lưu nháp mỗi 30 giây để giáo viên theo dõi.</template>
      </p>
      <button ref="panelToggle" type="button" class="panel-toggle" :class="{ closed: !panelOpen }"
              :disabled="!assignment || assignmentClosed"
              :title="panelOpen ? 'Thu gọn bảng trả lời' : 'Mở bảng trả lời'"
              :aria-label="panelOpen ? 'Thu gọn bảng trả lời' : 'Mở bảng trả lời'"
              :aria-expanded="panelOpen" aria-controls="answer-panel" @click="togglePanel">
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path v-if="panelOpen" d="M6 6l12 12M6 18L18 6" />
          <path v-else d="M4 4h16v16H4zM14 4v16M7 9h4M7 13h4" />
        </svg>
        <span>Trả lời {{ answered }}/{{ questions.length }}</span>
      </button>
    </div>

    <div v-if="error || sessionError || saveError" class="error" role="alert">
      <p v-if="error">{{ error }}</p>
      <p v-if="sessionError">{{ sessionError }}</p>
      <p v-if="saveError">{{ saveError }}</p>
    </div>
    <p v-if="assignmentClosed" class="closed-notice" role="status">
      Bài tập đã đóng hoặc chưa mở. Bạn không thể mở phiên làm việc, lưu hay nộp bài lúc này.
    </p>

    <div v-show="!assignmentClosed" class="workspace" :class="{ 'panel-open': panelOpen }">
      <div class="work" :inert="smallScreen && panelOpen">
        <!-- Only session lifecycle changes the src; panel toggles never unmount this iframe. -->
        <div v-if="embedUrl" class="jamovi-wrapper">
          <iframe :src="embedUrl" class="jamovi-frame" ref="frameEl" title="Không gian làm việc HeyStat"
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups" @load="refreshInstance" />
        </div>
        <div v-else-if="loadingAssignment || starting" class="loading">Đang khởi động phiên HeyStat…</div>
        <div v-else-if="submitSuccess" class="frozen">Đã nộp bài và đóng băng phiên làm việc.</div>
        <div v-else class="loading">{{ session ? noDatasetHint : 'Chưa mở được phiên HeyStat. Xem thông báo lỗi ở trên.' }}</div>
      </div>

      <button v-show="panelOpen" type="button" class="panel-backdrop" tabindex="-1"
              aria-label="Đóng bảng trả lời" @click="closePanel" />
      <aside v-show="panelOpen" id="answer-panel" class="side" aria-labelledby="answer-panel-title">
        <div class="side-header">
          <h2 id="answer-panel-title">Bài làm</h2>
          <button ref="panelClose" type="button" class="close-panel" aria-label="Đóng bảng trả lời" @click="closePanel">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M6 18L18 6" /></svg>
          </button>
        </div>
        <p class="tip">Có thể nộp đáp án hoặc bài tự luận mà không cần bảng kết quả. Nếu có phiên HeyStat, tệp .omv hiện tại sẽ được lưu kèm.</p>

        <section v-if="objectiveQuestions.length">
          <h2>Điền đáp án</h2>
          <div v-for="q in objectiveQuestions" :key="q.id" class="question">
            <label :for="`answer-${q.id}`">{{ q.label }}<span v-if="q.points" class="pts">{{ q.points }}đ</span></label>
            <input :id="`answer-${q.id}`" v-model="answers[q.id]" :type="q.type === 'number' ? 'number' : 'text'"
                   step="any" :readonly="!canEditAnswers" />
            <template v-if="q.comment">
              <label :for="`note-${q.id}`" class="note-label">{{ q.comment_hint || 'Lời giải / giải thích (không bắt buộc)' }}</label>
              <textarea :id="`note-${q.id}`" v-model="answers[noteKey(q.id)]" rows="4" class="note"
                        :readonly="!canEditAnswers" placeholder="Viết cách bạn làm, hoặc lý do chọn giá trị này…" />
            </template>
          </div>
        </section>

        <section v-if="essayQuestions.length">
          <h2>Tự luận / nhận xét</h2>
          <div v-for="q in essayQuestions" :key="q.id" class="question">
            <label :for="`essay-${q.id}`">{{ q.label }}<span v-if="q.points" class="pts">{{ q.points }}đ</span></label>
            <textarea :id="`essay-${q.id}`" v-model="answers[q.id]" rows="7" class="note"
                      :readonly="!canEditAnswers" placeholder="Viết bài tự luận hoặc nhận xét của bạn…" />
          </div>
        </section>

        <section v-if="tables.length" ref="evidencePanel">
          <h2>Bằng chứng (bảng / biểu đồ)</h2>
          <p class="tip">Chọn các bảng bạn muốn nộp kèm bài (không bắt buộc).</p>
          <label v-for="t in tables" :key="t.index" class="table-choice">
            <input type="checkbox" :value="t.index" v-model="selected" :disabled="!canWrite || busy"
                   @change="selectionEdited = true; selectionMessage = ''" />
            <span><strong>{{ t.title || 'Bảng' }}</strong><em v-if="t.analysis"> · {{ t.analysis }}</em></span>
          </label>
          <button class="small" :disabled="!canWrite || busy || !draftId" @click="saveSelection">
            {{ savingSelection ? 'Đang lưu…' : 'Lưu phần đã chọn' }}
          </button>
          <p v-if="selectionMessage" class="tip" role="status">{{ selectionMessage }}</p>
          <OutputTable v-for="t in chosen" :key="t.index" :table="t" />
        </section>
        <p v-else class="tip">Đồng bộ kết quả để xem và chọn bằng chứng, nếu có.</p>
        <p v-if="session && !instanceId" class="tip">{{ noDatasetHint }}</p>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'
import OutputTable from '@/components/OutputTable.vue'
import { sessionErrorMessage, useJamoviSession } from '@/composables/useJamoviSession'
import { usePresenceStore } from '@/stores/presence'

const route = useRoute()
const presence = usePresenceStore()
const classId = route.params.classId as string
const assignmentId = route.params.assignmentId as string

const assignment = ref<any>(null)
const loadingAssignment = ref(true)
const assignmentClosed = computed(() => assignment.value?.is_open === false)
const questions = ref<any[]>([])
const answers = ref<Record<string, string | number>>({})
const objectiveQuestions = computed(() => questions.value.filter(q => q.type !== 'essay'))
const essayQuestions = computed(() => questions.value.filter(q => q.type === 'essay'))

const panelOpen = ref(false)
const panelToggle = ref<HTMLButtonElement | null>(null)
const panelClose = ref<HTMLButtonElement | null>(null)
const evidencePanel = ref<HTMLElement | null>(null)
const screenQuery = window.matchMedia('(max-width: 900px)')
const smallScreen = ref(screenQuery.matches)
function updateScreen(event: MediaQueryListEvent) { smallScreen.value = event.matches }
async function openPanel() {
  panelOpen.value = true
  await nextTick()
  panelClose.value?.focus()
}
function closePanel() {
  if (!panelOpen.value) return
  panelOpen.value = false
  panelToggle.value?.focus()
}
function togglePanel() {
  if (panelOpen.value) closePanel()
  else void openPanel()
}
function handleEscape(event: KeyboardEvent) {
  if (!panelOpen.value) return
  event.stopPropagation()
  closePanel()
}

/** Explanations are independently editable, never the expected/graded value. */
const noteKey = (id: string) => `${id}_note`
const answered = computed(() => questions.value.filter(q => String(answers.value[q.id] ?? '').trim() !== '').length)
const hasAnswers = computed(() => Object.values(answers.value).some(value => String(value ?? '').trim() !== ''))

const tables = ref<any[]>([])
const selected = ref<number[]>([])
const selectionEdited = ref(false)
const selectionMessage = ref('')
const draftId = ref<string | null>(null)
const chosen = computed(() => tables.value.filter(t => selected.value.includes(t.index)))

const error = ref('')
const saveError = ref('')
const submitting = ref(false)
const syncing = ref(false)
const savingSelection = ref(false)
const autoSaving = ref(false)
const submitSuccess = ref(false)
const savedAt = ref<Date | null>(null)
const savedAnswers = ref<string | null>(null)
const answersChanged = computed(() => savedAnswers.value !== JSON.stringify(answers.value))

const {
  session, instanceId, embedUrl, captureName, error: sessionError, starting, capturing,
  frameEl, start, capture, refreshInstance, stop,
} = useJamoviSession()

const collabRole = computed(() => session.value?.collab_role)
// A loaded session is what the teacher's "đang làm bài" count means; answers typed
// without an editor still count as being in class, but not as working in HeyStat.
watch(session, (value) => { void presence.setEditing(!!value) })
const canWrite = computed(() => !!assignment.value && !assignmentClosed.value && !submitSuccess.value && collabRole.value === 'writer')
const busy = computed(() => loadingAssignment.value || starting.value || capturing.value || submitting.value || syncing.value || autoSaving.value || savingSelection.value)
const canEditAnswers = computed(() => canWrite.value && !submitting.value)
const canSync = computed(() => canWrite.value && !busy.value && (!!embedUrl.value || hasAnswers.value))
const canSubmit = computed(() => canSync.value)

const noDatasetHint = 'Bạn có thể trả lời và nộp bài ngay cả khi không có bộ dữ liệu. Có thể mở dữ liệu trong HeyStat hoặc nộp tệp từ "Tệp của tôi" ở chi tiết bài tập.'
function fmt(iso: string) { return new Date(iso).toLocaleString('vi-VN') }

/** Callers hold the shared busy guard through capture AND the server write. */
async function workForm() {
  const form = new FormData()
  if (refreshInstance()) {
    const { blob, report } = await capture()
    form.append('file', blob, captureName.value || 'submission.omv')
    form.append('report', report)
  } else if (!hasAnswers.value) {
    throw new Error('Hãy điền đáp án hoặc đợi phiên HeyStat sẵn sàng trước khi lưu / nộp bài.')
  }
  const answerSnapshot = JSON.stringify(answers.value)
  form.append('answers', answerSnapshot)
  return { form, answerSnapshot }
}

async function persistSnapshot() {
  const { form, answerSnapshot } = await workForm()
  form.append('assignment_id', assignmentId)
  if (draftId.value) form.append('draft_id', draftId.value)
  const { data } = await api.post('/sessions/snapshot', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  if (!data.id) throw new Error('Máy chủ chưa xác nhận bản nháp đã được lưu')
  draftId.value = data.id
  tables.value = data.outputs ?? []
  const available = tables.value.map(t => t.index)
  selected.value = selectionEdited.value ? selected.value.filter(index => available.includes(index)) : available
  selectionMessage.value = ''
  // Do not overwrite local answers: the student may have typed during the request.
  savedAnswers.value = answerSnapshot
  savedAt.value = new Date()
  saveError.value = ''
}

let autoSaveTimer: number | undefined
let active = true
async function autoSave() {
  if (!active || !canWrite.value || busy.value) return
  if (!refreshInstance() && !hasAnswers.value) return
  autoSaving.value = true
  try {
    await persistSnapshot()
  } catch (e: any) {
    saveError.value = `Tự lưu nháp thất bại: ${sessionErrorMessage(e, 'Không lưu được tiến độ')}`
  } finally { autoSaving.value = false }
}

async function syncResults() {
  if (!canSync.value) return
  error.value = ''
  saveError.value = ''
  syncing.value = true
  try {
    await persistSnapshot()
    if (active && tables.value.length) {
      await openPanel()
      evidencePanel.value?.scrollIntoView({ block: 'start' })
    }
  } catch (e: any) {
    saveError.value = `Đồng bộ thất bại: ${sessionErrorMessage(e, 'Không đồng bộ được kết quả')}`
  } finally { syncing.value = false }
}

async function saveSelection() {
  if (!canWrite.value || busy.value || !draftId.value) return
  savingSelection.value = true
  selectionMessage.value = ''
  try {
    await api.patch(`/assignments/${assignmentId}/submissions/${draftId.value}/outputs`, { selected: selected.value })
    selectionMessage.value = 'Đã lưu phần bằng chứng đã chọn.'
    saveError.value = ''
  } catch (e: any) {
    saveError.value = sessionErrorMessage(e, 'Không lưu được phần đã chọn')
  } finally { savingSelection.value = false }
}

async function submit() {
  if (!canSubmit.value) return
  error.value = ''
  saveError.value = ''
  submitting.value = true
  try {
    const { form } = await workForm()
    if (draftId.value) form.append('draft_id', draftId.value)
    if (selectionEdited.value) form.append('selected', JSON.stringify(selected.value))
    await api.post(`/assignments/${assignmentId}/submissions`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    submitSuccess.value = true
    clearInterval(autoSaveTimer)
    await stop()
  } catch (e: any) {
    error.value = sessionErrorMessage(e, 'Nộp bài thất bại')
  } finally { submitting.value = false }
}

onMounted(async () => {
  screenQuery.addEventListener('change', updateScreen)
  try {
    const { data } = await api.get(`/classes/${classId}/assignments/${assignmentId}`)
    if (!active) return
    assignment.value = data
    questions.value = data.questions ?? []
    if (assignmentClosed.value) return
    await start(assignmentId)
    if (!active) { await stop(); return }
    if (session.value) autoSaveTimer = window.setInterval(autoSave, 30000)
  } catch (e: any) {
    error.value = sessionErrorMessage(e, 'Không tải được bài tập')
  } finally { loadingAssignment.value = false }
})

onUnmounted(() => {
  active = false
  clearInterval(autoSaveTimer)
  screenQuery.removeEventListener('change', updateScreen)
  void presence.setEditing(false)
  if (!submitSuccess.value) void stop()
})
</script>

<style scoped>
.submit-page { display: flex; flex-direction: column; height: 100%; min-height: 0; gap: 0.4rem; }
.page-header { padding-left: 3.25rem; min-height: 44px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.25rem 0.75rem; }
.heading { display: flex; align-items: center; gap: 0.6rem; min-width: 0; flex: 1; }
.back { color: #666; text-decoration: none; font-size: 0.82rem; white-space: nowrap; }
h1 { margin: 0; font-size: 1.05rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badge { padding: 0.2rem 0.45rem; border-radius: 10px; font-size: 0.72rem; font-weight: 700; white-space: nowrap; }
.writer { background: #15803d; color: #fff; }
.observer { background: #9a3412; color: #fff; }
.metadata { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; font-size: 0.78rem; }
.deadline { color: #666; }
.helplink { color: #92400e; }
.toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 0.35rem 0.6rem; }
.actions { display: flex; gap: 0.4rem; }
.save-status { flex: 1; min-width: 8rem; color: #166534; font-size: 0.75rem; margin: 0; }
.workspace { position: relative; display: grid; grid-template-columns: minmax(0, 1fr); flex: 1; min-height: 0; overflow: hidden; }
.workspace.panel-open { grid-template-columns: minmax(0, 1fr) 21rem; gap: 0.5rem; }
.work { min-width: 0; min-height: 0; height: 100%; }
.jamovi-wrapper { height: 100%; border: 1px solid #ddd; border-radius: 4px; overflow: hidden; background: #fff; }
.jamovi-frame { display: block; width: 100%; height: 100%; border: none; }
.loading, .frozen { color: #666; padding: 2rem 1rem; text-align: center; }
.frozen { color: #15803d; border: 1px dashed #b7e4c7; border-radius: 8px; }
.side { display: flex; flex-direction: column; gap: 0.7rem; min-width: 0; min-height: 0; overflow: auto; padding: 0 0.65rem 1rem; border: 1px solid #ddd; border-radius: 6px; background: #fff; }
.side-header { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #eee; }
.side section { border: 1px solid #eee; border-radius: 8px; padding: 0.8rem; background: #fafafa; scroll-margin-top: 3rem; }
.side h2 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.side-header h2 { margin: 0; }
.tip { color: #666; font-size: 0.78rem; margin: 0 0 0.4rem; }
.question { margin-bottom: 0.75rem; }
.question:last-child { margin-bottom: 0; }
.question label { display: block; font-size: 0.82rem; margin-bottom: 0.25rem; }
.pts { float: right; color: #92400e; font-weight: 700; font-size: 0.75rem; }
.question input, .note { width: 100%; padding: 0.45rem 0.5rem; border: 1px solid #bbb; border-radius: 4px; box-sizing: border-box; font-size: 0.85rem; font-family: inherit; }
.question .note-label { color: #666; margin: 0.5rem 0 0.2rem; }
.note { resize: vertical; }
.table-choice { display: flex; gap: 0.4rem; align-items: baseline; font-size: 0.8rem; margin-bottom: 0.35rem; }
.table-choice em { color: #666; font-style: normal; }
button { min-height: 44px; padding: 0.45rem 0.75rem; background: #1a1a2e; color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 0.82rem; }
button.small { padding: 0.35rem 0.7rem; font-size: 0.78rem; }
button.secondary { background: #eee; color: #333; }
button:disabled { opacity: 0.55; cursor: not-allowed; }
button:focus-visible, input:focus-visible, textarea:focus-visible, a:focus-visible { outline: 3px solid #2563eb; outline-offset: 2px; }
.panel-toggle { display: flex; align-items: center; justify-content: center; gap: 0.4rem; margin-left: auto; background: #fffbeb; color: #92400e; border: 1px solid #d97706; }
.panel-toggle.closed { background: #1a1a2e; color: #fff; border-color: #1a1a2e; }
.panel-toggle svg, .close-panel svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; }
.close-panel { display: grid; place-items: center; width: 44px; padding: 0; color: #92400e; background: #fff; }
.panel-backdrop { display: none; }
.error { color: #b91c1c; font-size: 0.85rem; max-height: 5rem; overflow: auto; flex-shrink: 0; }
.error p { margin: 0.2rem 0; }
.closed-notice { padding: 1rem; border: 1px solid #d97706; border-radius: 6px; color: #92400e; background: #fffbeb; }
@media (max-width: 900px) {
  .workspace.panel-open { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .side { position: absolute; z-index: 3; inset: 0 0 0 auto; width: min(24rem, 100%); box-shadow: -4px 0 16px #0002; }
  .panel-backdrop { display: block; position: absolute; inset: 0; z-index: 2; border-radius: 0; padding: 0; background: #0005; }
  .save-status { flex-basis: 100%; order: 3; min-width: 0; }
  .metadata { font-size: 0.72rem; }
  .question input, .note { font-size: 1rem; }
}
@media (max-width: 420px) {
  .heading { flex-wrap: wrap; column-gap: 0.4rem; }
  h1 { flex-basis: 100%; order: 2; }
  .toolbar { column-gap: 0.25rem; }
  button { padding-right: 0.5rem; padding-left: 0.5rem; font-size: 0.78rem; }
  .panel-toggle { gap: 0.25rem; }
}
</style>
