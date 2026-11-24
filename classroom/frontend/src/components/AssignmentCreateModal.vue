<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal creator">
      <h2>Tạo bài tập mới</h2>

      <!-- ── 1. what the students must analyse ───────── -->
      <h4>Mẫu bài tập</h4>
      <div class="bp-row" v-for="g in BLUEPRINT_GROUPS" :key="g">
        <span class="bp-group">{{ g }}</span>
        <button v-for="b in byGroup(g)" :key="b.id" type="button" class="chip"
                :class="{ sel: bp === b.id }" :title="b.hint"
                @click="applyBlueprint(b)">{{ b.label }}</button>
      </div>
      <div class="bp-row">
        <span class="bp-group">Khác</span>
        <button type="button" class="chip" :class="{ sel: bp === 'blank' }" @click="applyBlueprint(BLANK_BLUEPRINT)">Tự cấu hình</button>
      </div>

      <!-- ── 2. basics ─────────────────────────────────── -->
      <h4>Thông tin</h4>
      <div class="field">
        <label>Tiêu đề <span class="req">*</span></label>
        <input class="form-input" v-model="form.title" placeholder="VD: Bài 3 — Kiểm định t một mẫu" />
      </div>
      <div class="field">
        <label>Hình thức</label>
        <div class="seg">
          <button v-for="t in TYPES" :key="t.value" type="button" class="chip"
                  :class="{ sel: form.assignment_type === t.value }"
                  @click="setType(t.value)">{{ t.label }}</button>
        </div>
        <p v-if="isExam" class="hint">
          Bài kiểm tra mới luôn ở trạng thái <strong>chưa mở</strong>. Sau khi chuẩn bị xong, giáo viên phải chủ động mở bài để học viên truy cập và làm bài.
        </p>
        <p v-else class="hint">Bài tập về nhà và bài thực hành được mở cho học viên ngay khi tạo.</p>
      </div>
      <div class="field">
        <label>Mô tả / yêu cầu gửi bài <span class="req">*</span></label>
        <textarea class="form-input" v-model="form.description" rows="6" />
        <span class="hint">Học viên thấy nội dung này cùng nút <em>Làm bài trong HeyStat</em>. Chọn lại mẫu ở trên sẽ khôi phục hướng dẫn.</span>
      </div>
      <div class="field-row">
        <div class="field">
          <label>Giờ bắt đầu</label>
          <input class="form-input" type="datetime-local" v-model="form.start_at" />
        </div>
        <div class="field">
          <label>Hạn nộp <span class="req">*</span></label>
          <input class="form-input" type="datetime-local" v-model="form.deadline" />
        </div>
        <div class="field">
          <label>Điểm tối đa</label>
          <input class="form-input" type="number" v-model.number="form.max_score" min="0" max="100" />
        </div>
      </div>
      <p class="hint">
        Giờ bắt đầu để trống nghĩa là học viên vào ngay khi bài được mở. Trước giờ này học viên chưa xem được đề,
        mở dữ liệu, làm bài hoặc nộp bài (giống như bài bị khoá).
      </p>

      <!-- ── 3. dataset ────────────────────────────────── -->
      <h4>Bộ dữ liệu</h4>
      <div class="row">
        <select class="form-input grow" v-model="form.file_id" @change="onFileChange">
          <option :value="null">Không kèm bộ dữ liệu (học viên tự dùng dữ liệu của mình)</option>
          <option v-for="f in files" :key="f.id" :value="f.id">{{ f.file_name }}</option>
        </select>
        <button class="btn-sm" type="button" :disabled="uploading" @click="dataInputRef?.click()">
          {{ uploading ? 'Đang tải lên…' : '+ Tải tệp lên' }}
        </button>
        <input ref="dataInputRef" type="file" style="display:none" @change="uploadAndPick" />
      </div>
      <p class="hint">
        Với bài chấm tự động, hãy đính kèm chính <strong>file .omv mẫu bạn đã chạy xong</strong> —
        HeyStat đọc được các bảng trong file đó và biến chúng thành tiêu chí chấm.
      </p>

      <p class="hint">
        Tệp mới tải lên tại đây được giữ riêng tư khi còn là bản nháp, kể cả khi huỷ tạo bài.
        Tệp đính kèm được mở cho học viên khi bài tập được mở; với bài kiểm tra, giáo viên phải mở bài sau khi tạo.
        Chọn tệp đã công khai không làm tệp đó riêng tư. Không thể thu hồi các bản học viên đã tải xuống trước đó.
      </p>

      <!-- ── 4. auto-grade checks ──────────────────────── -->
      <h4>Tiêu chí chấm tự động trên kết quả HeyStat</h4>
      <div class="row">
        <button class="btn-sm" type="button" @click="addCheck">+ Thêm tiêu chí</button>
        <button class="btn-sm" type="button" v-if="schema.length" @click="addAnalysisChecks">
          + Thêm phân tích từ file mẫu
        </button>
        <span class="meta" v-if="checks.length">
          {{ checks.length }} tiêu chí · {{ checkPoints }} điểm
        </span>
      </div>
      <p v-if="schemaError" class="error">{{ schemaError }}</p>
      <p class="hint" v-else-if="!schema.length && form.file_id">
        Tệp này không có bảng kết quả (khác định dạng .omv hoặc chưa chạy phân tích nào) — bạn vẫn có thể điền tay tên phân tích/bảng/cột.
      </p>
      <p class="hint" v-else-if="!schema.length">
        Chọn bộ dữ liệu ở trên để chọn tên phân tích/bảng/cột từ danh sách có sẵn.
      </p>

      <div v-for="(c, i) in checks" :key="i" class="block">
        <div class="row">
          <input v-model="c.label" class="grow" placeholder="Nhãn hiển thị cho học viên" />
          <select v-model="c.op">
            <option value="ran">Đã chạy phân tích</option>
            <option value="present">Bảng xuất hiện</option>
            <option value="lte">≤ giá trị</option>
            <option value="gte">≥ giá trị</option>
            <option value="lt">&lt; giá trị</option>
            <option value="gt">&gt; giá trị</option>
            <option value="eq">= giá trị (kèm sai số)</option>
            <option value="between">Trong khoảng</option>
          </select>
          <input v-model.number="c.points" class="num" type="number" step="0.25" title="Điểm" />
          <button class="btn-sm danger" type="button" @click="checks.splice(i, 1)">✕</button>
        </div>
        <div class="row">
          <select v-if="schema.length" v-model="c.analysis" @change="pickAnalysis(c)">
            <option value="">— Phân tích —</option>
            <option v-for="a in schema" :key="a.name" :value="a.name">{{ a.name }}</option>
          </select>
          <input v-else v-model="c.analysis" placeholder="Tên phân tích (vd. Linear Regression)" />
          <select v-if="schema.length && c.op !== 'ran'" v-model="c.table" @change="pickTable(c)">
            <option value="">— Bảng (bất kỳ) —</option>
            <option v-for="t in tablesOf(c)" :key="t.title" :value="t.title">{{ t.title }}</option>
          </select>
          <input v-else-if="c.op !== 'ran'" v-model="c.table" placeholder="Tên bảng (vd. Model Coefficients)" />
          <select v-if="schema.length && needsValue(c.op)" v-model="c.column">
            <option value="">— Cột —</option>
            <option v-for="col in columnsOf(c)" :key="col" :value="col">{{ col }}</option>
          </select>
          <input v-else-if="needsValue(c.op)" v-model="c.column" placeholder="Tên cột (vd. p)" />
          <select v-if="schema.length && needsValue(c.op)" v-model="c.row">
            <option value="">— Dòng đầu —</option>
            <option value="*">— Dòng cuối —</option>
            <option v-for="r in rowsOf(c)" :key="r" :value="r">{{ r }}</option>
          </select>
          <input v-else-if="needsValue(c.op)" v-model="c.row" placeholder="Dòng (vd. total effect, * = cuối)" />
        </div>
        <div class="row">
          <input v-if="needsValue(c.op)" v-model.number="c.value" class="num2" type="number" step="any" placeholder="Giá trị" />
          <input v-if="c.op === 'between'" v-model.number="c.value2" class="num2" type="number" step="any" placeholder="đến" />
          <input v-if="c.op === 'eq'" v-model.number="c.tolerance" class="num2" type="number" step="any" placeholder="± sai số" />
          <input v-model="c.explain" class="grow" placeholder="Giải thích khi học viên sai (vd. 'p phải ≤ .05')" />
        </div>
      </div>

      <!-- ── 5. sidebar questions ──────────────────────── -->
      <h4>Điền đáp án (chấm tự động)</h4>
      <div class="row">
        <button class="btn-sm" type="button" @click="addQuestion('number')">+ Thêm câu điền đáp án</button>
        <span class="meta" v-if="objectiveQuestions.length">
          {{ objectiveQuestions.length }} câu · {{ objectivePoints }} điểm tự động
        </span>
      </div>
      <p class="hint">
        Học viên không thấy đáp án bạn nhập ở đây. Có thể thêm ô lời giải tự do (không bắt buộc);
        học viên có thể viết lời giải ngay cả khi chưa điền đáp án. Lời giải không được chấm tự động.
      </p>
      <div v-for="q in objectiveQuestions" :key="q.id" class="block">
        <div class="row">
          <input v-model="q.label" class="grow" placeholder="VD: Giá trị trung bình của điểm số" />
          <select v-model="q.type" title="Loại đáp án">
            <option value="number">Số (± sai số)</option>
            <option value="text">Chữ (nhiều đáp án đúng)</option>
          </select>
          <input v-model="q.answer" class="mid"
                 :placeholder="q.type === 'number' ? 'Đáp án' : 'Đáp án (nhiều cách viết phân cách bằng ;)'" />
          <input v-if="q.type === 'number'" v-model.number="q.tolerance" class="num" type="number" step="any" title="Sai số cho phép" />
          <input v-model.number="q.points" class="num" type="number" step="0.25" title="Điểm tự động" />
          <button class="btn-sm danger" type="button" title="Xoá câu hỏi" @click="removeQuestion(q)">✕</button>
        </div>
        <div class="row">
          <input v-model="q.explain" class="grow" placeholder="Giải thích khi học viên trả lời sai (tuỳ chọn)" />
          <label class="chk"><input type="checkbox" v-model="q.comment" /> Thêm ô lời giải tự do (tuỳ chọn)</label>
          <input v-if="q.comment" v-model="q.comment_hint" class="grow"
                 placeholder="Nhãn hiển thị trên ô lời giải (vd. 'Cách bạn làm / lý do chọn giá trị này')" />
        </div>
      </div>

      <h4>Tự luận / nhận xét (giáo viên chấm)</h4>
      <div class="row">
        <button class="btn-sm" type="button" @click="addQuestion('essay')">+ Thêm câu tự luận / nhận xét</button>
        <span class="meta" v-if="essayQuestions.length">
          {{ essayQuestions.length }} câu · {{ manualPoints }} điểm giáo viên chấm
        </span>
      </div>
      <p class="hint">Học viên viết tự luận hoặc nhận xét. Không cần đáp án mẫu; giáo viên đọc bài và cho điểm.</p>
      <div v-for="q in essayQuestions" :key="q.id" class="block">
        <div class="row">
          <textarea v-model="q.label" class="form-input grow" rows="3" aria-label="Nội dung câu tự luận / nhận xét"
                    placeholder="VD: Nhận xét kết quả phân tích và giải thích ý nghĩa" />
          <input v-model.number="q.points" class="num" type="number" step="0.25" title="Điểm giáo viên chấm" />
          <button class="btn-sm danger" type="button" title="Xoá câu hỏi" @click="removeQuestion(q)">✕</button>
        </div>
      </div>

      <!-- ── 6. rules ──────────────────────────────────── -->
      <h4>Quy định nộp bài</h4>
      <div class="field">
        <label>Số người mỗi nhóm</label>
        <input class="form-input size" type="number" v-model.number="form.group_size" min="1" max="20" :disabled="isExam" />
        <span class="hint">= 1: mỗi học viên nộp một bài · &gt; 1: học viên lập nhóm và một người nộp thay cả nhóm.</span>
      </div>
      <label class="check-row">
        <input type="checkbox" v-model="form.allow_resubmit" :disabled="isExam" />
        Cho phép nộp lại nhiều lần trước hạn
      </label>
      <label class="check-row">
        <input type="checkbox" v-model="form.allow_sharing" :disabled="isExam" />
        Cho phép chia sẻ bài làm để tham khảo
      </label>
      <p class="hint" v-if="isExam">
        Bài kiểm tra không cho nộp lại, không chia sẻ và chỉ tính điểm file .omv học viên nộp lên.
      </p>

      <p class="total">
        Chấm tự động: <strong>{{ autoTotal }}</strong> điểm · Giáo viên chấm: <strong>{{ manualPoints }}</strong> điểm.
        <br />Tổng điểm tiêu chí: <strong>{{ rubricTotal }}</strong> · Điểm tối đa bài tập: {{ form.max_score }}.
        <span v-if="!checks.length && !questions.length" class="muted">Chưa có tiêu chí nên bài sẽ chấm tay.</span>
        <span v-else-if="rubricTotal !== Number(form.max_score)" class="muted">Điểm tiêu chí được quy về thang {{ form.max_score }} điểm.</span>
        <span v-if="essayQuestions.length" class="muted">Phần tự luận cần giáo viên cho điểm, không phải điểm tự động.</span>
      </p>
      <p v-if="error" class="error">{{ error }}</p>

      <div class="modal-actions">
        <button class="btn-secondary" type="button" @click="close">Huỷ</button>
        <button class="btn-primary" type="button" :disabled="saving || uploading" @click="create">
          {{ saving ? 'Đang tạo…' : 'Tạo bài tập' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import api from '@/api/client'
import {
  ASSIGNMENT_BLUEPRINTS, BLANK_BLUEPRINT, BLUEPRINT_GROUPS, checksOf, descriptionOf,
} from '@/utils/assignmentTemplates'

const TYPES = [
  { value: 'homework', label: 'Bài tập về nhà' },
  { value: 'project', label: 'Thực hành' },
  { value: 'exam', label: 'Kiểm tra' },
]

const props = defineProps<{ classId: string; files: any[]; show: boolean }>()
const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'created', a: any): void
  (e: 'uploaded', f: any): void
}>()

const bp = ref('')
const seededBy = ref('')
const saving = ref(false)
const uploading = ref(false)
const error = ref('')
const schema = ref<any[]>([])
const schemaError = ref('')
const dataInputRef = ref<HTMLInputElement | null>(null)

const defaultDeadline = () => {
  const d = new Date()
  d.setDate(d.getDate() + 7)
  d.setHours(23, 59, 0, 0)
  return localInput(d)
}
function localInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const blank = () => ({
  title: '',
  description: '',
  start_at: '',
  deadline: defaultDeadline(),
  max_score: 10,
  assignment_type: 'homework',
  file_id: null as string | null,
  group_size: 1,
  allow_resubmit: true,
  allow_sharing: false,
})
const form = reactive(blank())
const questions = reactive<any[]>([])
const checks = reactive<any[]>([])

const isExam = computed(() => form.assignment_type === 'exam')
const needsValue = (op: string) => !['ran', 'present'].includes(op)

const objectiveQuestions = computed(() => questions.filter((q) => q.type !== 'essay'))
const essayQuestions = computed(() => questions.filter((q) => q.type === 'essay'))
const sumPoints = (entries: any[]) => entries.reduce((sum, entry) => sum + (Number(entry.points) || 0), 0)
const checkPoints = computed(() => sumPoints(checks))
const objectivePoints = computed(() => sumPoints(objectiveQuestions.value))
const manualPoints = computed(() => sumPoints(essayQuestions.value))
const autoTotal = computed(() => checkPoints.value + objectivePoints.value)
const rubricTotal = computed(() => autoTotal.value + manualPoints.value)

const byGroup = (g: string) => ASSIGNMENT_BLUEPRINTS.filter((b) => b.group === g)

/** A blueprint fills the instructions and the checks the grader can score on its
 *  own; the teacher then edits or adds the rest. */
function applyBlueprint(b: any) {
  const edited = (checks.length > 0 || questions.length > 0) && seededBy.value !== b.id
  if (edited && !confirm('Mẫu này sẽ thay thế hướng dẫn và tiêu chí chấm bạn đang có. Tiếp tục?')) return
  bp.value = b.id
  seededBy.value = b.id
  form.description = descriptionOf(b)
  checks.splice(0, checks.length, ...checksOf(b))
  if (!form.title.trim()) form.title = b.id === 'blank' ? '' : b.label
}

function setType(v: string) {
  form.assignment_type = v
  if (v === 'exam') {
    form.group_size = 1
    form.allow_resubmit = false
    form.allow_sharing = false
  } else {
    form.allow_resubmit = true
  }
}

// randomUUID needs Safari 15.4; older teacher devices still fall back to a unique id.
const newId = (prefix: string) => `${prefix}_${crypto.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(36).slice(2)}`}`

function addQuestion(type: 'number' | 'essay') {
  const question = { id: newId('q'), label: '', type, points: 1 }
  questions.push(type === 'essay' ? question : {
    ...question, answer: null, tolerance: 0.001, explain: '', comment: false, comment_hint: '',
  })
}
function removeQuestion(question: any) {
  const index = questions.indexOf(question)
  if (index !== -1) questions.splice(index, 1)
}
function addCheck() { checks.push({ id: newId('c'), label: '', op: 'present', points: 1, explain: '' }) }

/** One "you must have run this analysis" check per analysis in the teacher's own
 *  solved file — the fastest way to turn a worked example into a rubric. */
function addAnalysisChecks() {
  for (const a of schema.value) {
    if (checks.some((c) => c.analysis === a.name)) continue
    checks.push({ id: newId('c'), label: a.name, op: 'ran', analysis: a.name, points: 1, explain: '' })
  }
}

/* The pickers are built from the attached .omv; a typed name that matches no
   rendered table grades nothing, so the schema drives the dropdowns. */
const tablesOf = (c: any) => (c.analysis
  ? schema.value.filter((a) => a.name === c.analysis)
  : schema.value
).flatMap((a: any) => a?.tables ?? [])
const selectedTable = (c: any) => tablesOf(c).find((t: any) => t.title === c.table)
const columnsOf = (c: any) => selectedTable(c)?.columns
  ?? [...new Set(tablesOf(c).flatMap((t: any) => t.columns))]
const rowsOf = (c: any) => selectedTable(c)?.row_labels
  ?? [...new Set(tablesOf(c).flatMap((t: any) => t.row_labels))]

function pickAnalysis(c: any) { c.table = ''; c.column = ''; c.row = '' }
function pickTable(c: any) { c.column = ''; c.row = '' }

async function loadSchema(fileId: string | null) {
  schema.value = []
  schemaError.value = ''
  if (!fileId) return
  try {
    const { data } = await api.get(`/classes/${props.classId}/files/${fileId}/omv-schema`)
    schema.value = data.analyses ?? []
  } catch (e: any) {
    if (e?.response?.status === 404) return
    schemaError.value = e?.response?.data?.detail
      ?? 'Không đọc được cấu trúc bảng từ tệp này — bạn phải điền tay tên phân tích/bảng/cột.'
  }
}

async function onFileChange() { await loadSchema(form.file_id) }

async function uploadAndPick(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('student_access', 'false')
    const { data } = await api.post(`/classes/${props.classId}/files`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    emit('uploaded', data)
    form.file_id = data.id
    await loadSchema(data.id)
  } catch (e: any) {
    error.value = detailText(e, 'Không tải được tệp lên')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

function serialiseQuestion(q: any) {
  if (q.type === 'essay') {
    const { answer, tolerance, explain, comment, comment_hint, ...question } = q
    return question
  }
  const answer = q.type === 'text' && typeof q.answer === 'string' && q.answer.includes(';')
    ? q.answer.split(';').map((s: string) => s.trim()).filter(Boolean)
    : q.answer
  return { ...q, answer }
}

function detailText(e: any, fallback: string) {
  const d = e?.response?.data?.detail
  return Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? fallback
}

async function create() {
  if (saving.value || uploading.value) return
  error.value = ''
  if (!form.title.trim()) { error.value = 'Vui lòng nhập tiêu đề'; return }
  if (!form.description.trim()) { error.value = 'Vui lòng nhập mô tả / yêu cầu gửi bài'; return }
  if (!form.deadline) { error.value = 'Vui lòng chọn hạn nộp'; return }
  if (form.start_at && new Date(form.start_at) >= new Date(form.deadline)) {
    error.value = 'Giờ bắt đầu phải trước hạn nộp'; return
  }
  saving.value = true
  try {
    const payload: any = {
      title: form.title.trim(),
      description: form.description,
      start_at: form.start_at ? new Date(form.start_at).toISOString() : null,
      deadline: new Date(form.deadline).toISOString(),
      max_score: Number(form.max_score) || 0,
      assignment_type: form.assignment_type,
      is_open: !isExam.value,
      file_id: form.file_id ?? undefined,
      group_size: isExam.value ? 1 : form.group_size,
      allow_resubmit: isExam.value ? false : form.allow_resubmit,
      allow_sharing: isExam.value ? false : form.allow_sharing,
      answer_key: questions.length
        ? { questions: questions.map(serialiseQuestion) }
        : undefined,
      grading_config: checks.length ? { checks } : undefined,
    }
    const { data } = await api.post(`/classes/${props.classId}/assignments`, payload)
    emit('created', data)
    close()
  } catch (e: any) {
    error.value = detailText(e, 'Không tạo được bài tập')
  } finally { saving.value = false }
}

function close() { emit('update:show', false) }

watch(() => props.show, (v) => {
  if (!v) return
  Object.assign(form, blank())
  questions.splice(0, questions.length)
  checks.splice(0, checks.length)
  schema.value = []
  schemaError.value = ''
  error.value = ''
  bp.value = BLANK_BLUEPRINT.id
  seededBy.value = BLANK_BLUEPRINT.id
})
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 500; padding: 1.5rem; box-sizing: border-box; }
.modal { background: #fff; border-radius: 14px; padding: 2rem; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.creator { max-width: 880px; max-height: 86vh; overflow-y: auto; }
.modal h2 { color: var(--amber-800); margin: 0 0 1rem; font-size: 1.1rem; font-weight: 700; }
h4 { margin: 1.4rem 0 0.6rem; font-size: 0.88rem; color: var(--amber-800); border-bottom: 1px solid var(--amber-200); padding-bottom: 0.3rem; }
.bp-row { display: flex; align-items: baseline; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 0.45rem; }
.bp-group { font-size: 0.75rem; font-weight: 700; color: var(--amber-700); min-width: 11rem; }
.seg { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.chip { font-size: 0.8rem; font-weight: 600; color: var(--amber-800); background: #fff; border: 1px solid var(--amber-300); border-radius: 16px; padding: 0.22rem 0.7rem; cursor: pointer; font-family: inherit; }
.chip:hover { border-color: var(--amber-500); }
.chip.sel { background: var(--amber-600); border-color: var(--amber-600); color: #fff; }
.field { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem; }
.field > label { font-size: 0.875rem; font-weight: 600; color: var(--amber-800); }
.field-row { display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end; }
.field-row .field { flex: 1; min-width: 10rem; }
.req { color: #DC2626; }
.form-input { padding: 0.45rem 0.65rem; border: 1px solid var(--amber-300); border-radius: 6px; font-size: 0.9rem; box-sizing: border-box; background: #fff; }
textarea.form-input { resize: vertical; font-family: inherit; }
.form-input.size { width: 8rem; }
.row { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.4rem; align-items: center; }
.block { border-bottom: 1px dashed var(--amber-200); padding-bottom: 0.5rem; margin-bottom: 0.6rem; }
input, select { padding: 0.35rem 0.5rem; border: 1px solid var(--amber-300); border-radius: 5px; font-size: 0.82rem; background: #fff; }
input { width: 9rem; }
select { max-width: 15rem; }
.grow { flex: 1; min-width: 12rem; }
.mid { width: 13rem; }
.chk { display: flex; align-items: center; gap: 0.3rem; font-size: 0.8rem; color: var(--amber-800); white-space: nowrap; }
.chk input { width: auto; }
.num { width: 4.5rem; }
.num2 { width: 6.5rem; }
.hint { color: var(--color-text-muted); font-size: 0.78rem; margin: 0.25rem 0 0; }
.meta { font-size: 0.78rem; color: var(--color-text-muted); }
.total { font-size: 0.85rem; color: var(--amber-800); margin: 1rem 0 0; }
.muted { color: var(--color-text-muted); font-size: 0.78rem; font-weight: 400; }
.check-row { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: var(--amber-800); }
.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; border: 1px solid var(--amber-400); background: #fff; color: var(--amber-800); border-radius: 5px; cursor: pointer; font-weight: 600; }
.btn-sm.danger { border-color: #FCA5A5; color: #B91C1C; }
.btn-sm:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #B91C1C; font-size: 0.82rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.4rem 0.6rem; border-radius: 6px; }
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem; }
</style>
