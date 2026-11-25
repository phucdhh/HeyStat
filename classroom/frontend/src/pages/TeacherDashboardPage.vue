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
        <div v-for="cls in classes" :key="cls.id" class="class-card" :class="{ 'menu-open': openMenu === cls.id }">
          <div class="cls-header">
            <div class="cls-title">{{ cls.title }}</div>
            <div class="cls-header-right">
              <span class="status-badge" :class="cls.status">{{ statusLabel(cls.status) }}</span>
              <div class="tool-wrap">
                <button class="tool-btn" type="button" aria-haspopup="menu"
                        :aria-expanded="openMenu === cls.id"
                        :aria-label="`Thao tác cho lớp ${cls.title}`"
                        title="Thao tác"
                        @click.stop="toggleMenu(cls.id)">⋮</button>
                <div v-if="openMenu === cls.id" class="tool-menu" role="menu" @click.stop>
                  <button class="menu-item" role="menuitem" @click="openRename(cls)">✏️ Đổi tên lớp</button>
                  <button class="menu-item" role="menuitem" @click="menuAnd(() => exportGrades(cls.id))">📊 Xuất bảng điểm</button>
                  <button class="menu-item" role="menuitem" @click="menuAnd(() => showKey(cls))">🔑 Mã lớp</button>
                  <button v-if="cls.status === 'draft'" class="menu-item" role="menuitem"
                          @click="menuAnd(() => toggleStatus(cls, 'active'))">✅ Kích hoạt lớp</button>
                  <button v-else-if="cls.status === 'active'" class="menu-item" role="menuitem"
                          @click="menuAnd(() => toggleStatus(cls, 'draft'))">🔒 Đóng tạm</button>
                  <div class="menu-sep"></div>
                  <button class="menu-item danger" role="menuitem" @click="menuAnd(() => askDelete(cls))">🗑️ Xoá lớp</button>
                </div>
              </div>
            </div>
          </div>
          <div class="cls-dates">
            <span>{{ fmtDate(cls.starts_at) }}</span> – <span>{{ fmtDate(cls.ends_at) }}</span>
          </div>
          <div class="cls-stats">
            <span class="stat" title="Số sinh viên đang tham gia lớp">👥 <strong>{{ cls.student_count ?? 0 }}</strong> sinh viên</span>
            <span class="stat" title="Số bài học trong lớp">📚 <strong>{{ cls.lesson_count ?? 0 }}</strong> bài học</span>
            <span class="stat" :class="{ dim: !cls.online_count }"
                  :title="`Số sinh viên đang mở trang lớp trong ${presenceWindow} giây gần nhất`">🟢 <strong>{{ cls.online_count ?? 0 }}</strong> online</span>
            <span class="stat" title="Số sinh viên đã nộp ít nhất một bài">✅ <strong>{{ cls.submitted_student_count ?? 0 }}</strong> đã nộp bài</span>
          </div>
          <div class="cls-meta">
            <RouterLink :to="`/classes/${cls.id}`">Xem lớp →</RouterLink>
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
    <ClassCreateModal :show="showCreate" @close="showCreate = false" @created="load" />

    <div v-if="copiedMsg" class="toast">{{ copiedMsg }}</div>
    <!-- Key display overlay -->
    <div v-if="keyClass" class="modal-overlay" @click.self="keyClass = null">
      <div class="modal key-modal">
        <h2>Mã lớp: {{ keyClass.title }}</h2>
        <p class="key-note" v-if="displayedKey">Học viên nhập mã này ở Lớp học → + Tham gia lớp.</p>
        <p class="key-note" v-else>Lớp này tạo trước khi có mã đọc lại được, nên chưa hiện mã cũ. Bấm “Đổi mã” để lấy mã mới rồi gửi cho học viên.</p>
        <div class="key-display">{{ displayedKey || '—' }}</div>
        <div class="modal-actions">
          <button class="btn-primary" :disabled="!displayedKey" @click="doCopyKey">📋 Sao chép</button>
          <button class="btn-secondary" @click="rotateKey">🔄 Đổi mã</button>
          <button class="btn-secondary" @click="keyClass = null">Đóng</button>
        </div>
      </div>
    </div>

    <!-- Delete class confirmation -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="closeDelete">
      <div class="modal">
        <h2>Xoá lớp “{{ deleteTarget.title }}”?</h2>
        <p v-if="deleteRisk">Những thứ sau sẽ mất theo lớp và không phục hồi được:</p>
        <p v-else class="risk-loading">Đang kiểm tra xem lớp đang có gì…</p>
        <ul v-if="deleteRisk && riskLines(deleteRisk).length" class="risk-list">
          <li v-for="line in riskLines(deleteRisk)" :key="line">{{ line }}</li>
        </ul>
        <p v-else-if="deleteRisk" class="risk-empty">Lớp này đang trống — chưa có bài tập, bài học hay học viên nào.</p>
        <p class="risk-note">Tài khoản học viên vẫn còn, chỉ dữ liệu trong lớp này bị xoá. Muốn tạm đóng mà giữ bài vở, dùng “🔒 Đóng tạm”.</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeDelete">Huỷ</button>
          <button class="btn-danger" :disabled="!deleteRisk || deleting" @click="doDelete">
            {{ deleting ? 'Đang xoá…' : 'Xoá vĩnh viễn' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Rename class modal -->
    <div v-if="renameTarget" class="modal-overlay" @click.self="closeRename">
      <div class="modal">
        <h2>Đổi tên lớp</h2>
        <div class="field">
          <label>Tên lớp mới <span class="req">*</span></label>
          <input class="form-input" v-model="renameTitle" maxlength="255"
                 placeholder="VD: Thống kê y học — Lớp K2024" @keyup.enter="doRename" />
        </div>
        <p v-if="renameError" class="error">{{ renameError }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" :disabled="renameSaving" @click="closeRename">Huỷ</button>
          <button class="btn-primary" :disabled="renameSaving || !renameTitle.trim()" @click="doRename">
            {{ renameSaving ? 'Đang lưu…' : 'Lưu tên mới' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/api/client'
import ClassCreateModal from '@/components/ClassCreateModal.vue'
import { downloadFile } from '@/utils/download'

const classes = ref<any[]>([])
const loading = ref(true)
const activeTab = ref('classes')
const selectedClass = ref<string | null>(null)
const progress = ref<any>(null)
const progressLoading = ref(false)
const showCreate = ref(false)
const copiedMsg = ref('')
const displayedKey = ref('')
const keyClass = ref<any>(null)
const deleteTarget = ref<any>(null)
const deleteRisk = ref<any>(null)
const deleting = ref(false)
const openMenu = ref<string | null>(null)
const renameTarget = ref<any>(null)
const renameTitle = ref('')
const renameError = ref('')
const renameSaving = ref(false)
// Same window as the presence router: a beat older than this is "offline".
const presenceWindow = 90
let statsTimer: number | undefined

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

/** Refresh the live counters without flashing the whole page. */
async function refreshStats() {
  if (document.visibilityState !== 'visible') return
  try {
    const { data } = await api.get('/classes')
    for (const fresh of data) {
      const cls = classes.value.find(c => c.id === fresh.id)
      if (!cls) continue
      cls.title = fresh.title
      cls.status = fresh.status
      cls.student_count = fresh.student_count
      cls.lesson_count = fresh.lesson_count
      cls.online_count = fresh.online_count
      cls.submitted_student_count = fresh.submitted_student_count
    }
  } catch {
    // Keep the last numbers; presence is live, not an error state.
  }
}

function toggleMenu(id: string) {
  openMenu.value = openMenu.value === id ? null : id
}

function closeMenu() {
  openMenu.value = null
}

function menuAnd(action: () => void | Promise<void>) {
  closeMenu()
  void action()
}

function openRename(cls: any) {
  closeMenu()
  renameTarget.value = cls
  renameTitle.value = cls.title
  renameError.value = ''
}

function closeRename() {
  if (renameSaving.value) return
  renameTarget.value = null
  renameError.value = ''
}

async function doRename() {
  const cls = renameTarget.value
  const title = renameTitle.value.trim()
  if (!cls || !title || renameSaving.value) return
  if (title === cls.title) { closeRename(); return }
  renameSaving.value = true
  renameError.value = ''
  try {
    const { data } = await api.patch(`/classes/${cls.id}`, { title })
    cls.title = data.title ?? title
    renameTarget.value = null
    copiedMsg.value = 'Đã đổi tên lớp.'
    setTimeout(() => (copiedMsg.value = ''), 3000)
  } catch (e: any) {
    const d = e?.response?.data?.detail
    renameError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d ?? 'Không đổi được tên lớp'
  } finally {
    renameSaving.value = false
  }
}

async function loadProgress() {
  if (!selectedClass.value) return
  progressLoading.value = true
  try {
    const { data } = await api.get(`/classes/${selectedClass.value}/progress`)
    progress.value = data
  } finally { progressLoading.value = false }
}

function statusLabel(s: string) {
  return s === 'active' ? 'Đang mở' : s === 'draft' ? 'Chưa mở' : s === 'archived' ? 'Lưu trữ' : s
}

async function toggleStatus(cls: any, newStatus: string) {
  try {
    await api.patch(`/classes/${cls.id}`, { status: newStatus })
    cls.status = newStatus
    copiedMsg.value = newStatus === 'active' ? 'Lớp đã kích hoạt — học viên có thể tham gia!' : 'Lớp đã đóng tạm.'
    setTimeout(() => (copiedMsg.value = ''), 3000)
  } catch {}
}

async function showKey(cls: any) {
  try {
    const { data } = await api.get(`/classes/${cls.id}/enrollment-code`)
    displayedKey.value = data.enrollment_code ?? ''
    keyClass.value = cls
  } catch {
    copiedMsg.value = 'Không lấy được mã lớp'
    setTimeout(() => (copiedMsg.value = ''), 2000)
  }
}

async function rotateKey() {
  const cls = keyClass.value
  if (!cls) return
  const warning = displayedKey.value
    ? `Đổi mã lớp “${cls.title}”?\n\nMã ${displayedKey.value} hết hiệu lực ngay; học viên đã vào lớp vẫn ở trong lớp.`
    : `Lấy mã lớp mới cho “${cls.title}”?`
  if (!confirm(warning)) return
  try {
    const { data } = await api.put(`/classes/${cls.id}/enrollment-code`, { enrollment_code: null })
    displayedKey.value = data.enrollment_code
  } catch {
    copiedMsg.value = 'Không đổi được mã lớp'
    setTimeout(() => (copiedMsg.value = ''), 2000)
  }
}

async function doCopyKey() {
  try {
    await navigator.clipboard.writeText(displayedKey.value)
    copiedMsg.value = 'Đã sao chép mã lớp!'
    setTimeout(() => (copiedMsg.value = ''), 2000)
  } catch {}
}

function riskLines(r: any): string[] {
  const lines: string[] = []
  if (r.students) lines.push(`${r.students} học viên đang tham gia`)
  if (r.assignments || r.submissions) lines.push(`${r.assignments} bài tập với ${r.submissions} bài nộp`)
  if (r.lessons) lines.push(`${r.lessons} bài học`)
  if (r.quizzes) lines.push(`${r.quizzes} bài kiểm tra`)
  if (r.files) lines.push(`${r.files} tệp dữ liệu`)
  return lines
}

function closeDelete() {
  deleteTarget.value = null
  deleteRisk.value = null
}

async function askDelete(cls: any) {
  deleteTarget.value = cls
  deleteRisk.value = null
  try {
    const { data } = await api.get(`/classes/${cls.id}/risk`)
    deleteRisk.value = data
  } catch {
    closeDelete()
    copiedMsg.value = 'Không kiểm tra được dữ liệu của lớp'
    setTimeout(() => (copiedMsg.value = ''), 2500)
  }
}

async function doDelete() {
  const cls = deleteTarget.value
  if (!cls || !deleteRisk.value || deleting.value) return
  deleting.value = true
  try {
    await api.delete(`/classes/${cls.id}`)
    classes.value = classes.value.filter(x => x.id !== cls.id)
    if (selectedClass.value === cls.id) {
      selectedClass.value = classes.value[0]?.id ?? null
      progress.value = null
      if (selectedClass.value) loadProgress()
    }
    closeDelete()
    copiedMsg.value = `Đã xoá lớp “${cls.title}”.`
    setTimeout(() => (copiedMsg.value = ''), 3000)
  } catch (e: any) {
    copiedMsg.value = e?.response?.data?.detail ?? 'Không xoá được lớp'
    setTimeout(() => (copiedMsg.value = ''), 3000)
  } finally {
    deleting.value = false
  }
}

async function exportGrades(classId: string) {
  try {
    await downloadFile(`/classes/${classId}/grades/export`, `bang_diem_${classId}.csv`)
  } catch {
    copiedMsg.value = 'Không tải được bảng điểm'
    setTimeout(() => (copiedMsg.value = ''), 3000)
  }
}

onMounted(() => {
  document.addEventListener('click', closeMenu)
  void load()
  statsTimer = window.setInterval(refreshStats, 20000)
})

onUnmounted(() => {
  document.removeEventListener('click', closeMenu)
  if (statsTimer) clearInterval(statsTimer)
})
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
.class-card { position: relative; background: #fff; border: 1.5px solid var(--amber-200); border-radius: 10px; padding: 1.1rem; box-shadow: 0 1px 4px var(--color-card-shadow); }
.class-card.menu-open { z-index: 30; }
.cls-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.3rem; }
.cls-title { font-weight: 700; color: var(--amber-800); overflow-wrap: anywhere; }
.cls-header-right { display: flex; align-items: center; gap: 0.35rem; flex-shrink: 0; }
.tool-wrap { position: relative; }
.tool-btn { width: 26px; height: 26px; border-radius: 6px; border: 1px solid transparent; background: transparent; color: var(--amber-700); font-size: 1.1rem; line-height: 1; cursor: pointer; padding: 0; }
.tool-btn:hover, .tool-btn[aria-expanded="true"] { background: var(--amber-100); border-color: var(--amber-300); }
.tool-menu { position: absolute; right: 0; top: calc(100% + 4px); z-index: 50; min-width: 195px; background: #fff; border: 1px solid var(--amber-200); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.16); padding: 0.3rem; text-align: left; }
.menu-item { display: block; width: 100%; text-align: left; border: none; background: transparent; padding: 0.45rem 0.6rem; border-radius: 5px; cursor: pointer; font-size: 0.85rem; color: #333; font-family: inherit; }
.menu-item:hover { background: var(--amber-50); }
.menu-item.danger { color: #B91C1C; }
.menu-item.danger:hover { background: #FEE2E2; }
.menu-sep { height: 1px; background: var(--amber-100); margin: 0.25rem 0; }
.cls-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.3rem 0.8rem; margin: 0.55rem 0 0.65rem; font-size: 0.78rem; color: var(--color-text-muted); }
.cls-stats .stat { white-space: nowrap; }
.cls-stats strong { color: var(--amber-800); }
.cls-stats .dim { opacity: 0.65; }
.status-badge { font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 10px; }
.status-badge.active { background: #D1FAE5; color: #065F46; }
.status-badge.draft { background: #FEF3C7; color: #92400E; }
.status-badge.archived { background: #F3F4F6; color: #6B7280; }
.btn-sm.activate { background: #D1FAE5; color: #065F46; border-color: #6EE7B7; }
.btn-sm.activate:hover { background: #A7F3D0; }
.btn-sm.close-btn { background: #FEE2E2; color: #991B1B; border-color: #FCA5A5; }
.btn-sm.close-btn:hover { background: #FECACA; }
.btn-sm.delete { background: #fff; color: #B91C1C; border-color: #FCA5A5; }
.btn-sm.delete:hover { background: #FEE2E2; }
.btn-danger { background: #DC2626; color: #fff; border: none; padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-danger:hover { background: #B91C1C; }
.btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }
.risk-loading, .risk-empty { font-size: 0.9rem; color: var(--color-text-muted); margin: 0 0 1rem; }
.risk-list { margin: 0 0 1rem; padding-left: 1.3rem; }
.risk-list li { font-size: 0.9rem; line-height: 1.7; }
.risk-note { font-size: 0.82rem; color: var(--color-text-muted); margin: 0; }
.key-modal { text-align: center; }
.key-note { font-size: 0.85rem; color: var(--color-text-muted); margin: 0 0 1rem; }
.key-display { font-size: 1.6rem; font-weight: 800; letter-spacing: 0.2em; color: var(--amber-800); background: var(--amber-50); padding: 1rem; border-radius: 8px; border: 2px dashed var(--amber-300); margin-bottom: 1.25rem; font-family: monospace; }
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
