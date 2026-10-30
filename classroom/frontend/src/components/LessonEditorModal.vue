<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal editor">
      <h2>{{ lesson ? 'Sửa bài học' : 'Tạo bài học mới' }}</h2>

      <!-- ── 1. format ─────────────────────────────────── -->
      <h4>Loại bài học</h4>
      <div class="type-grid">
        <button v-for="t in LESSON_TYPES" :key="t.value" type="button" class="type-card"
                :class="{ sel: form.lesson_type === t.value }" @click="setType(t.value)">
          <span class="t-icon">{{ t.icon }}</span>
          <span class="t-label">{{ t.label }}</span>
          <span class="t-hint">{{ t.hint }}</span>
        </button>
      </div>
      <p class="hint">Trang học viên của bài “{{ activeType.label }}” sẽ mở đầu bằng {{ activeType.leadsWith }}.</p>

      <!-- ── 2. basics ─────────────────────────────────── -->
      <h4>Nội dung</h4>
      <div class="field">
        <label>Tiêu đề <span class="req">*</span></label>
        <input class="form-input" v-model="form.title" placeholder="Bài 1: Giới thiệu thống kê mô tả…" />
      </div>
      <div class="row outline-row">
        <span class="hint grow">Khởi đầu:</span>
        <button type="button" class="chip" :class="{ sel: !usedOutline }" @click="applyOutline(BLANK_OUTLINE)">Tự viết</button>
        <button type="button" class="chip" @click="applyOutline(OUTLINES[form.lesson_type])">Bố cục mẫu</button>
      </div>

      <div class="toolbar">
        <button type="button" title="Đề mục" @click="wrap('## ', '')">H2</button>
        <button type="button" title="Chữ đậm" @click="wrap('**', '**')"><strong>B</strong></button>
        <button type="button" title="Chữ nghiêng" @click="wrap('*', '*')"><em>I</em></button>
        <button type="button" title="Danh sách" @click="wrap('- ', '')">•</button>
        <button type="button" title="Liên kết" @click="wrap('[', '](https://)')">🔗</button>
        <button type="button" title="Công thức LaTeX" @click="wrap('$', '$')">∑</button>
        <button type="button" title="Đoạn mã" @click="wrap('```\n', '\n```')">{'{ }'}</button>
        <button type="button" class="preview-btn" :class="{ sel: showPreview }" @click="showPreview = !showPreview">
          {{ showPreview ? '✕ Ẩn xem trước' : '👁 Xem trước' }}
        </button>
      </div>
      <div class="write" :class="{ split: showPreview }">
        <textarea class="form-input md" ref="bodyRef" v-model="form.content" rows="12"
                  placeholder="## Nội dung bài học…" />
        <div v-if="showPreview" class="preview" v-html="rendered"></div>
      </div>

      <!-- ── 3. attachments ────────────────────────────── -->
      <h4>Tài nguyên đính kèm</h4>
      <div v-if="resources.length" class="res-list">
        <div v-for="(r, i) in resources" :key="r.id ?? `new-${i}`" class="res-row">
          <span class="res-icon">{{ iconOf(r.resource_type) }}</span>
          <span class="res-title">{{ r.title || r.url || fileNameOf(r.file_id) }}</span>
          <button type="button" class="btn-icon" title="Bỏ đính kèm" @click="removeResource(i)">🗑️</button>
        </div>
      </div>
      <div v-else class="hint">Chưa đính kèm gì.</div>

      <div class="res-add">
        <div class="row">
          <select class="form-input" v-model="draft.resource_type">
            <option v-for="t in RESOURCE_TYPES" :key="t.value" :value="t.value">{{ t.icon }} {{ t.label }}</option>
          </select>
          <input class="form-input grow" v-model="draft.title" placeholder="Nhãn hiển thị (tuỳ chọn)" />
        </div>
        <div class="row">
          <input v-if="draft.resource_type !== 'data_file'" class="form-input grow" v-model="draft.url"
                 placeholder="https://youtube.com/watch?v=… hoặc https://drive.google.com/…" />
          <select v-else class="form-input grow" v-model="draft.file_id">
            <option :value="null">Chọn bộ dữ liệu trong lớp…</option>
            <option v-for="f in files" :key="f.id" :value="f.id">{{ f.file_name }}</option>
          </select>
          <button type="button" class="btn-sm" @click="addResource">+ Đính kèm</button>
        </div>
        <p class="hint">{{ EMBED_HINT }}</p>
      </div>

      <div class="field-row">
        <div class="field">
          <label>Thứ tự hiển thị</label>
          <input class="form-input" type="number" v-model.number="form.sort_order" min="0" />
        </div>
        <div class="field check-field">
          <label class="check-row">
            <input type="checkbox" v-model="form.is_published" /> Công khai để học viên thấy
          </label>
        </div>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <div class="modal-actions">
        <button class="btn-secondary" @click="close">Huỷ</button>
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Đang lưu…' : lesson ? 'Lưu thay đổi' : 'Tạo bài học' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import api from '@/api/client'
import { useMarkdown } from '@/composables/useMarkdown'
import {
  BLANK_OUTLINE, EMBED_HINT, LESSON_TYPES, OUTLINES, RESOURCE_TYPES, lessonTypeOf,
} from '@/utils/lessonTemplates'

const props = defineProps<{ classId: string; lesson: any | null; files: any[]; show: boolean }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void; (e: 'saved', l: any): void }>()

const { renderMarkdown } = useMarkdown()
const bodyRef = ref<HTMLTextAreaElement | null>(null)
const saving = ref(false)
const error = ref('')
const showPreview = ref(false)
const usedOutline = ref(false)
const resources = ref<any[]>([])
const draft = reactive<{ resource_type: string; title: string; url: string; file_id: string | null }>(
  { resource_type: 'video', title: '', url: '', file_id: null },
)

const form = reactive({
  title: '', content: '', lesson_type: 'standard', sort_order: 0, is_published: false,
})

const activeType = computed(() => lessonTypeOf(form.lesson_type))
const rendered = computed(() => renderMarkdown(form.content))

const iconOf = (t: string) => RESOURCE_TYPES.find(r => r.value === t)?.icon ?? '📎'
const fileNameOf = (id: string | null) => props.files.find(f => f.id === id)?.file_name ?? ''

// Choosing the practical format is how a teacher says "this lesson has a dataset",
// so the attachment draft follows it without another click.
watch(() => form.lesson_type, (t) => {
  draft.resource_type = t === 'practical' ? 'data_file' : t === 'video' ? 'video' : draft.resource_type
})

watch(() => props.show, async (open) => {
  if (!open) return
  error.value = ''
  showPreview.value = false
  usedOutline.value = false
  const l = props.lesson
  Object.assign(form, {
    title: l?.title ?? '',
    content: l?.content ?? '',
    lesson_type: l?.lesson_type ?? 'standard',
    sort_order: l?.sort_order ?? 0,
    is_published: !!l?.is_published,
  })
  resources.value = []
  if (l?.id) {
    try {
      const { data } = await api.get(`/classes/${props.classId}/lessons/${l.id}`)
      resources.value = data.resources.map((r: any) => ({ ...r, existing: true }))
    } catch { /* the body still edits fine without the attachment list */ }
  }
})

function setType(v: string) {
  form.lesson_type = v
  if (!form.content.trim()) applyOutline(OUTLINES[v])
}

function applyOutline(make: (title: string) => string) {
  usedOutline.value = true
  form.content = make(form.title.trim() || 'Bài học')
}

function wrap(open: string, close: string) {
  const el = bodyRef.value
  const s = el?.selectionStart ?? form.content.length
  const e = el?.selectionEnd ?? form.content.length
  const inside = form.content.slice(s, e)
  form.content = form.content.slice(0, s) + open + inside + close + form.content.slice(e)
  requestAnimationFrame(() => {
    el?.focus()
    el?.setSelectionRange(s + open.length, s + open.length + inside.length)
  })
}

function addResource() {
  error.value = ''
  const type = draft.resource_type
  if (type === 'data_file') {
    if (!draft.file_id) { error.value = 'Hãy chọn bộ dữ liệu .omv của lớp'; return }
    resources.value.push({
      resource_type: type, title: draft.title, file_id: draft.file_id,
      sort_order: resources.value.length, pending: true,
    })
  } else {
    const url = draft.url.trim()
    if (!/^https?:\/\//.test(url)) { error.value = 'Liên kết phải bắt đầu bằng http:// hoặc https://'; return }
    resources.value.push({
      resource_type: type, title: draft.title, url,
      sort_order: resources.value.length, pending: true,
    })
  }
  Object.assign(draft, { title: '', url: '', file_id: null })
}

function removeResource(i: number) {
  const [gone] = resources.value.splice(i, 1)
  // A row that already exists on the server has to be deleted there, not just hidden.
  if (gone?.existing) {
    api.delete(`/classes/${props.classId}/lessons/${props.lesson.id}/resources/${gone.id}`).catch(() => {})
  }
}

function payload() {
  return {
    title: form.title.trim(),
    content: form.content,
    lesson_type: form.lesson_type,
    sort_order: form.sort_order,
    is_published: form.is_published,
  }
}

async function save() {
  error.value = ''
  if (!form.title.trim()) { error.value = 'Vui lòng nhập tiêu đề'; return }
  saving.value = true
  try {
    let saved
    if (props.lesson?.id) {
      saved = (await api.patch(`/classes/${props.classId}/lessons/${props.lesson.id}`, payload())).data
    } else {
      saved = (await api.post(`/classes/${props.classId}/lessons`, payload())).data
      saved.resource_count = 0
    }
    for (const r of resources.value.filter(x => x.pending)) {
      await api.post(`/classes/${props.classId}/lessons/${saved.id}/resources`, {
        resource_type: r.resource_type, title: r.title || null,
        url: r.url || null, file_id: r.file_id || null, sort_order: r.sort_order,
      })
    }
    saved.resource_count = resources.value.length
    emit('saved', saved)
    close()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    error.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Lỗi khi lưu bài học'
  } finally { saving.value = false }
}

function close() { emit('update:show', false) }
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 500; padding: 1.5rem; }
.modal { background: #fff; border-radius: 14px; padding: 1.75rem 2rem; width: 100%; max-width: 860px; max-height: 92vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal h2 { color: var(--amber-800); margin: 0 0 1rem; font-size: 1.1rem; font-weight: 700; }
h4 { margin: 1.25rem 0 0.5rem; font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--amber-600); }
.type-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 0.6rem; }
.type-card { display: flex; flex-direction: column; gap: 0.2rem; text-align: left; padding: 0.7rem 0.8rem; border: 1.5px solid var(--amber-200); background: #fff; border-radius: 10px; cursor: pointer; }
.type-card:hover { border-color: var(--amber-400); }
.type-card.sel { border-color: var(--amber-500); background: var(--amber-50); box-shadow: 0 0 0 2px var(--amber-200); }
.t-icon { font-size: 1.15rem; }
.t-label { font-weight: 700; color: var(--amber-900); font-size: 0.9rem; }
.t-hint { font-size: 0.75rem; color: var(--color-text-muted); line-height: 1.35; }
.field { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem; }
.field > label { font-size: 0.875rem; font-weight: 600; color: var(--amber-800); }
.field-row { display: flex; gap: 1rem; align-items: flex-end; }
.field-row .field { flex: 1; }
.check-field { justify-content: flex-end; }
.req { color: #DC2626; }
.form-input { width: 100%; padding: 0.45rem 0.65rem; border: 1px solid var(--amber-300); border-radius: 6px; font-size: 0.9rem; box-sizing: border-box; }
.form-input:focus { outline: none; border-color: var(--amber-500); }
textarea.form-input.md { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; line-height: 1.5; resize: vertical; }
.row { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; }
.grow { flex: 1; }
.outline-row { margin-bottom: 0.75rem; }
.toolbar { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.5rem; }
.toolbar button { min-width: 2rem; padding: 0.25rem 0.55rem; font-size: 0.82rem; border: 1px solid var(--amber-300); background: var(--amber-50); color: var(--amber-800); border-radius: 6px; cursor: pointer; }
.toolbar button:hover { background: var(--amber-100); }
.toolbar .preview-btn.sel { background: var(--amber-600); color: #fff; border-color: var(--amber-600); }
.write { display: grid; gap: 0.75rem; grid-template-columns: 1fr; }
.write.split { grid-template-columns: 1fr 1fr; }
.preview { border: 1px solid var(--amber-200); border-radius: 8px; padding: 0.75rem 0.9rem; overflow-y: auto; max-height: 22rem; font-size: 0.88rem; background: var(--amber-50); }
.chip { font-size: 0.75rem; font-weight: 600; padding: 0.22rem 0.6rem; border-radius: 999px; border: 1px solid var(--amber-300); background: #fff; color: var(--amber-800); cursor: pointer; }
.chip.sel { background: var(--amber-200); }
.res-list { border: 1px solid var(--amber-200); border-radius: 8px; padding: 0.35rem 0.6rem; margin-bottom: 0.6rem; }
.res-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0; font-size: 0.85rem; }
.res-title { flex: 1; color: var(--amber-900); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.res-add { border-top: 1px dashed var(--amber-200); padding-top: 0.6rem; }
.btn-sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; border: 1px solid var(--amber-300); background: var(--amber-50); color: var(--amber-800); border-radius: 5px; cursor: pointer; font-weight: 600; }
.btn-sm:hover { background: var(--amber-100); }
.btn-icon { background: transparent; border: none; cursor: pointer; opacity: 0.55; font-size: 0.9rem; }
.btn-icon:hover { opacity: 1; }
.hint { font-size: 0.78rem; color: var(--color-text-muted); margin: 0.35rem 0 0; line-height: 1.4; }
.check-row { display: flex; align-items: center; gap: 0.45rem; font-size: 0.875rem; color: var(--amber-800); }
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem; }
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.4rem 0.6rem; border-radius: 6px; margin: 0.6rem 0 0; }
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
</style>
