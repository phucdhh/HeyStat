<template>
  <section class="grading">
    <div class="head">
      <h3>Tiêu chí chấm tự động</h3>
      <button class="btn-sm" :disabled="saving" @click="save">
        {{ saving ? 'Đang lưu…' : 'Lưu tiêu chí' }}
      </button>
    </div>
    <p class="hint">
      Học viên chỉ thấy câu hỏi, không thấy đáp án. Nếu bạn không cấu hình gì, bài nộp vẫn chấm tay như trước.
    </p>

    <h4>Phần 1 – Câu hỏi trên thanh bên</h4>
    <div v-for="(q, i) in questions" :key="i" class="block">
      <div class="row">
        <input v-model="q.label" class="grow" placeholder="Nội dung câu hỏi" />
        <select v-model="q.type">
          <option value="number">Số</option>
          <option value="text">Chữ</option>
        </select>
        <input v-model="q.answer" class="mid" :placeholder="q.type === 'number' ? 'Đáp án' : 'Đáp án (nhiều cách viết phân cách bằng ;)'" />
        <input v-if="q.type === 'number'" v-model.number="q.tolerance" class="num" type="number" step="any" title="Sai số cho phép" />
        <input v-model.number="q.points" class="num" type="number" step="0.25" title="Điểm" />
        <button class="btn-sm danger" @click="questions.splice(i, 1)">✕</button>
      </div>
      <div class="row">
        <input v-model="q.explain" class="grow" placeholder="Giải thích khi học viên trả lời sai" />
      </div>
    </div>
    <div class="row">
      <button class="btn-sm" @click="addQuestion">+ Thêm câu hỏi</button>
    </div>

    <h4>Phần 2 – Tiêu chí trên bảng kết quả HeyStat</h4>
    <p v-if="schemaError" class="error">{{ schemaError }}</p>
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
        <button class="btn-sm danger" @click="checks.splice(i, 1)">✕</button>
      </div>

      <!-- Pickers built from the teacher's own file: a typed name that does not
           match a rendered table silently grades nothing. -->
      <div v-if="schema.length" class="row">
        <select v-model="c.analysis" @change="pickAnalysis(c)">
          <option value="">— Phân tích —</option>
          <option v-for="a in schema" :key="a.name" :value="a.name">{{ a.name }}</option>
        </select>
        <select v-if="c.op !== 'ran'" v-model="c.table" @change="pickTable(c)">
          <option value="">— Bảng (bất kỳ) —</option>
          <option v-for="t in tablesOf(c)" :key="t.title" :value="t.title">{{ t.title }}</option>
        </select>
        <select v-if="needsValue(c.op)" v-model="c.column">
          <option value="">— Cột —</option>
          <option v-for="col in columnsOf(c)" :key="col" :value="col">{{ col }}</option>
        </select>
        <select v-if="needsValue(c.op)" v-model="c.row">
          <option value="">— Dòng đầu —</option>
          <option value="*">— Dòng cuối —</option>
          <option v-for="r in rowsOf(c)" :key="r" :value="r">{{ r }}</option>
        </select>
      </div>
      <div v-else class="row">
        <input v-model="c.analysis" placeholder="Tên phân tích (vd. Linear Regression)" />
        <input v-model="c.table" placeholder="Tên bảng (vd. Model Coefficients)" />
        <input v-model="c.column" placeholder="Tên cột (vd. p)" />
        <input v-model="c.row" placeholder="Dòng (vd. total effect, * = cuối)" />
      </div>

      <div class="row">
        <input v-if="needsValue(c.op)" v-model.number="c.value" class="num2" type="number" step="any" placeholder="Giá trị" />
        <input v-if="c.op === 'between'" v-model.number="c.value2" class="num2" type="number" step="any" placeholder="đến" />
        <input v-if="c.op === 'eq'" v-model.number="c.tolerance" class="num2" type="number" step="any" placeholder="± sai số" />
        <input v-model="c.explain" class="grow" placeholder="Giải thích khi học viên sai (gd. 'p phải ≤ .05')" />
      </div>
    </div>
    <div class="row">
      <button class="btn-sm" @click="addCheck">+ Thêm tiêu chí</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="saved">✓ Đã lưu tiêu chí chấm.</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import api from '@/api/client'

const props = defineProps<{
  classId: string
  assignmentId: string
  answerKey: Record<string, any> | null
  gradingConfig: Record<string, any> | null
}>()

const questions = reactive<any[]>([])
const checks = reactive<any[]>([])
const schema = ref<any[]>([])
const schemaError = ref('')
const saving = ref(false)
const saved = ref(false)
const error = ref('')

function needsValue(op: string) {
  return !['ran', 'present'].includes(op)
}

/** Mirrors omv_reader.normalise(), the folding the grader itself uses, so a check
 *  saved as "R2" still lands on the "R²" column instead of an empty dropdown. */
const FOLD: Record<string, string> = {
  '²': '2', '³': '3', 'α': 'a', 'β': 'b', 'ρ': 'r', 'η': 'n', 'χ': 'chi',
  'μ': 'mu', 'σ': 's', '−': '-', '≤': '<=', '≥': '>=', '×': 'x',
}
const fold = (text: string) => String(text).replace(/[²³αβρηχμσ−≤≥×]/g, (c) => FOLD[c])
  .toLowerCase().replace(/[^a-z0-9]+/g, '')

function pick(options: string[], value: string) {
  if (!value) return value
  return options.find((o) => o === value)
    ?? options.find((o) => fold(o) === fold(value))
    ?? options.find((o) => fold(o).includes(fold(value)))
    ?? value
}

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

async function loadSchema() {
  schemaError.value = ''
  try {
    const { data } = await api.get(`/assignments/${props.assignmentId}/grading-schema`)
    schema.value = data.analyses ?? []
    // old checks may store a module key (linReg) or a folded name (R2): show what they mean
    checks.forEach((c) => {
      const hit = schema.value.find((a) => a.name === c.analysis || a.module === c.analysis)
      if (hit) c.analysis = hit.name
      c.table = pick(tablesOf(c).map((t: any) => t.title), c.table)
      c.column = pick(columnsOf(c), c.column)
      c.row = pick(rowsOf(c), c.row)
    })
  } catch (e: any) {
    if (e?.response?.status !== 404) {
      schemaError.value = 'Không đọc được cấu trúc bảng từ bộ dữ liệu của bài tập — bạn phải điền tay tên phân tích/bảng/cột.'
    }
  }
}

function load() {
  questions.splice(0, questions.length, ...(props.answerKey?.questions ?? []).map((q: any) => ({ ...q })))
  checks.splice(0, checks.length, ...(props.gradingConfig?.checks ?? []).map((c: any) => ({ ...c })))
  loadSchema()
}
watch(() => [props.answerKey, props.gradingConfig], load, { immediate: true })
onMounted(loadSchema)

function addQuestion() {
  questions.push({ id: `q${questions.length + 1}`, label: '', type: 'number', answer: null, tolerance: 0.001, points: 1, explain: '' })
}

function addCheck() {
  checks.push({ id: `c${checks.length + 1}`, label: '', op: 'present', points: 1, explain: '' })
}

/** The grader reads a list of accepted spellings for text answers. */
function normaliseAnswer(q: any) {
  if (q.type !== 'text' || typeof q.answer !== 'string' || !q.answer.includes(';')) return q.answer
  return q.answer.split(';').map((s: string) => s.trim()).filter(Boolean)
}

async function save() {
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    await api.patch(`/classes/${props.classId}/assignments/${props.assignmentId}`, {
      answer_key: questions.length ? { questions: questions.map((q) => ({ ...q, answer: normaliseAnswer(q) })) } : null,
      grading_config: checks.length ? { checks } : null,
    })
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Không lưu được tiêu chí'
  } finally { saving.value = false }
}
</script>

<style scoped>
.grading { border: 1px solid var(--amber-200); border-radius: 10px; padding: 1rem; background: var(--amber-50); margin-bottom: 1.75rem; }
.head { display: flex; justify-content: space-between; align-items: center; }
h3, h4 { margin: 0 0 0.5rem; color: var(--amber-800); }
h4 { margin-top: 1.1rem; font-size: 0.9rem; }
.hint { color: var(--color-text-muted); font-size: 0.8rem; margin: 0.35rem 0 0; }
.row { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.4rem; }
.block { border-bottom: 1px dashed var(--amber-200); padding-bottom: 0.5rem; margin-bottom: 0.6rem; }
input, select { padding: 0.32rem 0.5rem; border: 1px solid var(--amber-300); border-radius: 5px; font-size: 0.82rem; }
input { width: 9rem; }
.grow { flex: 1; min-width: 12rem; }
.mid { width: 13rem; }
.num { width: 4rem; }
.num2 { width: 6.5rem; }
.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; border: 1px solid var(--amber-400); background: #fff; color: var(--amber-800); border-radius: 5px; cursor: pointer; font-weight: 600; }
.btn-sm.danger { border-color: #FCA5A5; color: #B91C1C; }
.btn-sm:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #B91C1C; font-size: 0.82rem; }
.saved { color: #059669; font-size: 0.82rem; }
</style>
