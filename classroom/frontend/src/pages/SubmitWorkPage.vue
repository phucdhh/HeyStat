<template>
  <div>
    <RouterLink :to="`/classes/${classId}/assignments/${assignmentId}`" class="back">← Quay lại bài tập</RouterLink>
    <div class="page-header">
      <h1>{{ assignment?.title ?? 'Nộp bài' }}</h1>
      <span v-if="collabRole === 'writer'" class="badge writer">✏️ Writer</span>
      <span v-else-if="collabRole === 'observer'" class="badge observer">👁 Observer (xem)</span>
      <span v-if="assignment" class="deadline">Hạn: {{ fmt(assignment.deadline) }}</span>
    </div>
    <p class="hint">
      <template v-if="collabRole === 'observer'">
        Bạn đang xem bài làm của nhóm. Chỉ trưởng nhóm (Writer) mới nộp được bài.
      </template>
      <template v-else>
        Làm việc trong HeyStat bên cạnh, nhấn <strong>Đồng bộ kết quả</strong> để chọn bảng/biểu đồ
        làm bằng chứng, rồi <strong>Nộp bài</strong>. Phiên làm việc được tự lưu mỗi 30 giây.
      </template>
    </p>
    <RouterLink to="/help" class="helplink">📖 Cách đọc bảng kết quả</RouterLink>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="layout" :class="{ rail: !panelOpen }">
      <div class="work">
        <div v-if="embedUrl" class="jamovi-wrapper">
          <iframe :src="embedUrl" class="jamovi-frame" ref="frameEl"
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
        </div>
        <div v-else-if="starting" class="loading">Đang khởi động phiên HeyStat…</div>
        <div v-else-if="submitSuccess" class="frozen">✓ Phiên làm việc đã đóng băng sau khi nộp bài.</div>
        <div v-else class="loading">{{ noDatasetHint }}</div>
        <p v-if="autoSavedAt" class="autosave">✓ Phiên được tự lưu lúc {{ autoSavedAt.toLocaleTimeString('vi-VN') }}</p>
      </div>

      <aside class="side" :class="{ rail: !panelOpen }">
        <button class="panel-toggle" :class="{ closed: !panelOpen }"
                :title="panelOpen ? 'Thu gọn bảng trả lời' : 'Mở bảng trả lời'"
                :aria-expanded="panelOpen" @click="togglePanel">
          {{ panelOpen ? '−' : '☰' }}
        </button>

        <p v-if="!panelOpen" class="rail-counts">
          <span class="rc">¶ {{ answered }}/{{ questions.length }}</span>
          <span class="rc">▤ {{ selected.length }}/{{ tables.length }}</span>
        </p>

        <template v-if="panelOpen">
          <section v-if="questions.length">
            <h2>Phần 1 – Trả lời</h2>
            <div v-for="q in questions" :key="q.id" class="question">
              <label>{{ q.label }}<span v-if="q.points" class="pts">{{ q.points }}đ</span></label>
              <input v-if="q.type === 'number'" v-model="answers[q.id]" type="number" step="any" />
              <textarea v-else-if="q.type === 'essay'" v-model="answers[q.id]" rows="7" class="note"
                        placeholder="Viết câu trả lời của bạn ở đây…" />
              <input v-else v-model="answers[q.id]" type="text" />
              <label v-if="q.comment" class="note-label">{{ q.comment_hint || 'Lời giải / giải thích' }}</label>
              <textarea v-if="q.comment" v-model="answers[noteKey(q.id)]" rows="4" class="note"
                        placeholder="Viết cách bạn làm, hoặc lý do chọn giá trị này…" />
            </div>
          </section>

          <section v-if="tables.length">
            <h2>Phần 2 – Bằng chứng (bảng / biểu đồ)</h2>
            <p class="tip">Chọn các bảng bạn muốn nộp kèm bài.</p>
            <label v-for="t in tables" :key="t.index" class="table-choice">
              <input type="checkbox" :value="t.index" v-model="selected" />
              <span><strong>{{ t.title || 'Bảng' }}</strong><em v-if="t.analysis"> · {{ t.analysis }}</em></span>
            </label>
            <button class="small" :disabled="savingSelection || !selected.length" @click="saveSelection">
              {{ savingSelection ? 'Đang lưu…' : 'Lưu phần đã chọn' }}
            </button>
            <OutputTable v-for="t in chosen" :key="t.index" :table="t" />
          </section>

          <p v-if="session && !instanceId" class="tip">{{ noDatasetHint }}</p>

          <div v-if="collabRole !== 'observer'" class="actions">
            <button class="secondary" :disabled="!canSync" @click="syncResults">
              {{ syncing ? 'Đang đồng bộ…' : '🔄 Đồng bộ kết quả' }}
            </button>
            <button :disabled="!canSubmit" @click="submit">
              {{ submitting ? 'Đang nộp…' : 'Nộp bài' }}
            </button>
          </div>
          <p v-if="submitSuccess" class="success">✓ Đã nộp và đóng băng phiên làm việc.</p>
        </template>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'
import OutputTable from '@/components/OutputTable.vue'
import { useJamoviSession } from '@/composables/useJamoviSession'

const route = useRoute()
const classId = route.params.classId as string
const assignmentId = route.params.assignmentId as string

const assignment = ref<any>(null)
const questions = ref<any[]>([])
const answers = ref<Record<string, string>>({})

// The panel covers half the spreadsheet, so its width is remembered per browser.
const PANEL_KEY = 'heystat.submit.panel'
const panelOpen = ref(localStorage.getItem(PANEL_KEY) !== 'closed')
function togglePanel() {
  panelOpen.value = !panelOpen.value
  localStorage.setItem(PANEL_KEY, panelOpen.value ? 'open' : 'closed')
}

/** Free-text explanations travel with the answers but are never graded as a value. */
const noteKey = (id: string) => `${id}_note`
const answered = computed(
  () => questions.value.filter(q => String(answers.value[q.id] ?? '').trim() !== '').length,
)

const tables = ref<any[]>([])
const selected = ref<number[]>([])
const draftId = ref<string | null>(null)
const chosen = computed(() => tables.value.filter((t) => selected.value.includes(t.index)))

const error = ref('')
const submitting = ref(false)
const syncing = ref(false)
const savingSelection = ref(false)
const submitSuccess = ref(false)
const autoSavedAt = ref<Date | null>(null)

const { session, instanceId, embedUrl, captureName, starting, capturing, frameEl, start, capture, stop } = useJamoviSession()

const collabRole = computed(() => session.value?.collab_role ?? 'writer')
const busy = computed(() => starting.value || capturing.value || submitting.value || syncing.value)
const canSync = computed(() => collabRole.value !== 'observer' && !!instanceId.value && !busy.value)
const canSubmit = computed(() => canSync.value && tables.value.length > 0)

const noDatasetHint =
  'Bài tập này không kèm bộ dữ liệu. Vào phần chi tiết bài tập để nộp một tệp trong "Tệp của tôi".'

function fmt(iso: string) {
  return new Date(iso).toLocaleString('vi-VN')
}

let autoSaveTimer: number | undefined
async function autoSave() {
  if (submitSuccess.value || !instanceId.value) return
  try {
    await capture()
    autoSavedAt.value = new Date()
  } catch {
    // a failed background save must never interrupt the student's work
  }
}

async function syncResults() {
  error.value = ''
  syncing.value = true
  try {
    const { blob, report } = await capture()
    const form = new FormData()
    form.append('assignment_id', assignmentId)
    form.append('file', blob, captureName.value || 'submission.omv')
    if (report) form.append('report', report)
    const { data } = await api.post(`/sessions/snapshot`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    draftId.value = data.id
    tables.value = data.outputs ?? []
    if (!selected.value.length) selected.value = tables.value.map((t: any) => t.index)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Không đồng bộ được kết quả'
  } finally { syncing.value = false }
}

async function saveSelection() {
  if (!draftId.value) return
  savingSelection.value = true
  try {
    const { data } = await api.patch(
      `/assignments/${assignmentId}/submissions/${draftId.value}/outputs`,
      { selected: selected.value },
    )
    tables.value = data.outputs ?? tables.value
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Không lưu được phần đã chọn'
  } finally { savingSelection.value = false }
}

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const { blob, report } = await capture()
    const form = new FormData()
    form.append('file', blob, captureName.value || 'submission.omv')
    if (report) form.append('report', report)
    if (Object.keys(answers.value).length) form.append('answers', JSON.stringify(answers.value))
    if (tables.value.length) form.append('selected', JSON.stringify(selected.value))
    const { data } = await api.post(`/assignments/${assignmentId}/submissions`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    submitSuccess.value = true
    await stop()
    embedUrl.value = null
  } catch (e: any) {
    const d = e?.response?.data?.detail
    error.value = typeof d === 'string' ? d : 'Nộp bài thất bại'
  } finally { submitting.value = false }
}

onMounted(async () => {
  try {
    const { data } = await api.get(`/classes/${classId}/assignments/${assignmentId}`)
    assignment.value = data
    questions.value = data.questions ?? []
  } catch {}
  await start(assignmentId)
  if (!session.value) error.value = error.value || 'Không mở được phiên HeyStat'
  autoSaveTimer = window.setInterval(autoSave, 30000)
})

onUnmounted(() => {
  if (autoSaveTimer) clearInterval(autoSaveTimer)
  if (!submitSuccess.value) stop()
})
</script>

<style scoped>
.back { color: #666; text-decoration: none; font-size: 0.9rem; }
.page-header { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin: 0.5rem 0 0.3rem; }
h1 { margin: 0; font-size: 1.4rem; }
.badge { padding: 0.25rem 0.65rem; border-radius: 12px; font-size: 0.82rem; font-weight: 700; }
.writer { background: #27ae60; color: #fff; }
.observer { background: #e67e22; color: #fff; }
.deadline { color: #666; font-size: 0.85rem; }
.hint { color: #666; font-size: 0.9rem; margin: 0.4rem 0; max-width: 60rem; }
.helplink { display: inline-block; font-size: 0.85rem; color: #92400e; margin-bottom: 0.6rem; }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 22rem; gap: 1rem; align-items: start; }
.layout.rail { grid-template-columns: minmax(0, 1fr) 3.5rem; }
.jamovi-wrapper { border: 1px solid #ddd; border-radius: 4px; overflow: hidden; }
.jamovi-frame { width: 100%; height: 78vh; border: none; }
.autosave { color: #15803d; font-size: 0.78rem; margin: 0.4rem 0 0; }
.loading { color: #888; padding: 2rem 0; text-align: center; }
.frozen { color: #15803d; padding: 2rem 0; text-align: center; border: 1px dashed #b7e4c7; border-radius: 8px; }
.side { display: flex; flex-direction: column; gap: 1rem; }
.side section { border: 1px solid #eee; border-radius: 8px; padding: 0.8rem; background: #fafafa; }
.side h2 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.tip { color: #777; font-size: 0.78rem; margin: 0 0 0.5rem; }
.question { margin-bottom: 0.6rem; }
.question label { display: block; font-size: 0.82rem; margin-bottom: 0.2rem; }
.pts { float: right; color: #92400e; font-weight: 700; font-size: 0.75rem; }
.question input { width: 100%; padding: 0.35rem 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
.note-label { display: block; font-size: 0.76rem; color: #666; margin: 0.4rem 0 0.15rem; }
.note { width: 100%; padding: 0.35rem 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 0.82rem; font-family: inherit; resize: vertical; }
.table-choice { display: flex; gap: 0.4rem; align-items: baseline; font-size: 0.8rem; margin-bottom: 0.35rem; }
.table-choice em { color: #888; font-style: normal; }
.panel-toggle { align-self: flex-end; width: 2rem; height: 2rem; padding: 0; border: 1px solid #ccc; border-radius: 6px; background: #fff; color: #555; font-size: 1.05rem; line-height: 1; }
.panel-toggle:hover { background: #f0f0f0; }
.panel-toggle.closed { background: #1a1a2e; color: #fff; border-color: #1a1a2e; }
.rail-counts { display: flex; flex-direction: column; gap: 0.4rem; margin: 0; }
.rail-counts .rc { font-size: 0.78rem; color: #666; text-align: center; }
.actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
button { padding: 0.6rem 1.1rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 0.92rem; }
button.small { padding: 0.35rem 0.7rem; font-size: 0.78rem; }
button.secondary { background: #f0f0f0; color: #333; }
button:disabled { opacity: 0.55; cursor: not-allowed; }
.success { color: green; font-weight: 600; margin: 0; }
.error { color: #b91c1c; margin-bottom: 0.6rem; }
@media (max-width: 1100px) { .layout, .layout.rail { grid-template-columns: 1fr; } }
</style>
