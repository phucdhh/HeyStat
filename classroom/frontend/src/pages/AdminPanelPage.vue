<template>
  <div class="admin-page">
    <h1>Quản trị hệ thống</h1>

    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key">
        {{ tab.label }}
      </button>
    </div>

    <!-- Users tab -->
    <div v-if="activeTab === 'users'">
      <div class="toolbar">
        <p class="meta">Tổng: {{ usersTotal }} người dùng</p>
        <button class="btn-primary" @click="showCreateModal = true">+ Thêm người dùng</button>
      </div>
      <div v-if="usersLoading" class="loading">Đang tải…</div>
      <div v-else>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th style="width:48px">Avatar</th>
                <th>Họ tên</th>
                <th>Email</th>
                <th>Vai trò</th>
                <th>Trạng thái</th>
                <th>Cấp quyền</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td>
                  <div class="avatar-cell">
                    <img v-if="u.avatar_url" :src="`/api/v1/auth/avatar/${u.avatar_url}`" class="avatar-img" :alt="u.full_name" />
                    <div v-else class="avatar-initial">{{ (u.full_name || u.email || '?')[0].toUpperCase() }}</div>
                  </div>
                </td>
                <td>{{ u.full_name }}</td>
                <td class="email-cell">{{ u.email }}</td>
                <td>
                  <span class="role-badge" :class="effectiveRole(u.roles)">{{ roleLabelVi(effectiveRole(u.roles)) }}</span>
                </td>
                <td>
                  <span class="status-badge" :class="u.is_active ? 'active' : 'inactive'">
                    {{ u.is_active ? 'Hoạt động' : 'Bị khoá' }}
                  </span>
                </td>
                <td class="actions">
                  <select class="role-select" :value="effectiveRole(u.roles)"
                          @change="setRole(u.id, ($event.target as HTMLSelectElement).value)">
                    <option value="user">Người dùng</option>
                    <option value="teacher">Giáo viên</option>
                    <option value="admin">Quản trị</option>
                  </select>
                  <button class="btn-sm" :class="u.is_active ? 'danger' : ''"
                          @click="toggleActive(u)">{{ u.is_active ? 'Khoá' : 'Mở khoá' }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="pagination">
          <button :disabled="usersPage <= 1" @click="loadUsers(usersPage - 1)">‹ Trước</button>
          <span>Trang {{ usersPage }}</span>
          <button :disabled="users.length < usersPageSize" @click="loadUsers(usersPage + 1)">Sau ›</button>
        </div>
      </div>
    </div>

    <!-- Stats tab -->
    <div v-if="activeTab === 'stats'">
      <div v-if="statsLoading" class="loading">Đang tải…</div>
      <div v-else-if="stats" class="stats-grid">
        <div class="stat-card"><div class="stat-val">{{ stats.total_users }}</div><div class="stat-lbl">Người dùng</div></div>
        <div class="stat-card"><div class="stat-val">{{ stats.total_classes }}</div><div class="stat-lbl">Lớp học</div></div>
        <div class="stat-card"><div class="stat-val">{{ stats.total_submissions }}</div><div class="stat-lbl">Bài nộp</div></div>
      </div>
    </div>

    <!-- Settings tab -->
    <div v-if="activeTab === 'settings'">
      <div v-if="settingsLoading" class="loading">Đang tải…</div>
      <div v-else class="settings-list">
        <div v-for="s in settings" :key="s.key" class="setting-row">
          <label>{{ s.key }}</label>
          <input class="form-input" v-model="s.value" @blur="saveSetting(s)" />
        </div>
      </div>
    </div>

    <!-- Create User Modal -->
    <div v-if="showCreateModal" class="modal-backdrop" @click.self="closeCreateModal">
      <div class="modal">
        <h2>Thêm người dùng mới</h2>
        <form @submit.prevent="createUser">
          <div class="field">
            <label>Email <span class="required">*</span></label>
            <input type="email" class="form-input" v-model="newUser.email" required placeholder="email@example.com" />
          </div>
          <div class="field">
            <label>Họ và tên <span class="required">*</span></label>
            <input type="text" class="form-input" v-model="newUser.full_name" required placeholder="Nguyễn Văn A" />
          </div>
          <div class="field">
            <label>Mật khẩu <span class="required">*</span></label>
            <input type="password" class="form-input" v-model="newUser.password" required
                   placeholder="Tối thiểu 8 ký tự, có chữ và số" autocomplete="new-password" />
          </div>
          <div class="field">
            <label>Vai trò</label>
            <div class="role-radios">
              <label class="radio-label" v-for="r in roleOptions" :key="r.value">
                <input type="radio" :value="r.value" v-model="newUser.role" />
                <span class="radio-text">
                  <strong>{{ r.label }}</strong>
                  <small>{{ r.desc }}</small>
                </span>
              </label>
            </div>
          </div>
          <div v-if="createError" class="alert-error">{{ createError }}</div>
          <div v-if="createOk" class="alert-success">Tạo người dùng thành công!</div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="closeCreateModal">Huỷ</button>
            <button type="submit" class="btn-primary" :disabled="creating">
              {{ creating ? 'Đang tạo…' : 'Tạo người dùng' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import api from '@/api/client'

const tabs = [
  { key: 'users', label: 'Người dùng' },
  { key: 'stats', label: 'Thống kê' },
  { key: 'settings', label: 'Cài đặt' },
]
const activeTab = ref('users')

const users = ref<any[]>([])
const usersTotal = ref(0)
const usersPage = ref(1)
const usersPageSize = 20
const usersLoading = ref(false)

const stats = ref<any>(null)
const statsLoading = ref(false)

const settings = ref<any[]>([])
const settingsLoading = ref(false)

const showCreateModal = ref(false)
const creating = ref(false)
const createError = ref('')
const createOk = ref(false)

const roleOptions = [
  { value: 'user', label: 'Người dùng', desc: 'Tham gia lớp, nộp bài tập' },
  { value: 'teacher', label: 'Giáo viên', desc: 'Tạo lớp, quản lý học viên' },
  { value: 'admin', label: 'Quản trị', desc: 'Toàn quyền hệ thống' },
]

const newUser = ref({ email: '', full_name: '', password: '', role: 'user' })

function effectiveRole(roles: string[]): string {
  if (!roles || !roles.length) return 'user'
  if (roles.includes('admin')) return 'admin'
  if (roles.includes('teacher')) return 'teacher'
  return 'user'
}

function roleLabelVi(role: string): string {
  return { user: 'Người dùng', teacher: 'Giáo viên', admin: 'Quản trị' }[role] ?? role
}

function closeCreateModal() {
  showCreateModal.value = false
  createError.value = ''
  createOk.value = false
  newUser.value = { email: '', full_name: '', password: '', role: 'user' }
}

async function createUser() {
  creating.value = true
  createError.value = ''
  createOk.value = false
  // Build hierarchical roles to send: admin → admin+teacher+user, teacher → teacher+user, user → user
  const roleMap: Record<string, string[]> = {
    user: ['user'],
    teacher: ['user', 'teacher'],
    admin: ['user', 'teacher', 'admin'],
  }
  try {
    await api.post('/admin/users', {
      email: newUser.value.email,
      full_name: newUser.value.full_name,
      password: newUser.value.password,
      roles: roleMap[newUser.value.role] ?? ['user'],
    })
    createOk.value = true
    await loadUsers(usersPage.value)
    setTimeout(closeCreateModal, 1200)
  } catch (err: any) {
    const d = err.response?.data?.detail
    createError.value = Array.isArray(d) ? d.map((x: any) => x.msg).join(', ') : d || 'Tạo người dùng thất bại'
  } finally {
    creating.value = false
  }
}

async function loadUsers(page = 1) {
  usersLoading.value = true
  usersPage.value = page
  try {
    const { data } = await api.get('/admin/users', { params: { page, size: usersPageSize } })
    users.value = data.items
    usersTotal.value = data.total
  } finally {
    usersLoading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try { const { data } = await api.get('/admin/stats'); stats.value = data }
  finally { statsLoading.value = false }
}

async function loadSettings() {
  settingsLoading.value = true
  try { const { data } = await api.get('/admin/settings'); settings.value = data }
  finally { settingsLoading.value = false }
}

async function setRole(userId: string, targetRole: string) {
  // Hierarchical: admin > teacher > user
  // What roles to ensure exist and what to remove
  const toGrant: Record<string, string[]> = { user: ['user'], teacher: ['user', 'teacher'], admin: ['user', 'teacher', 'admin'] }
  const toRevoke: Record<string, string[]> = { user: ['teacher', 'admin'], teacher: ['admin'], admin: [] }

  for (const r of toRevoke[targetRole] ?? []) {
    await api.delete(`/admin/users/${userId}/roles/${r}`).catch(() => {})
  }
  for (const r of toGrant[targetRole] ?? []) {
    await api.post(`/admin/users/${userId}/roles/${r}`).catch(() => {})
  }
  await loadUsers(usersPage.value)
}

async function toggleActive(u: any) {
  await api.patch(`/admin/users/${u.id}`, null, { params: { is_active: !u.is_active } })
  await loadUsers(usersPage.value)
}

async function saveSetting(s: any) {
  await api.put('/admin/settings', { [s.key]: s.value })
}

onMounted(() => loadUsers())
watch(activeTab, (tab) => {
  if (tab === 'stats' && !stats.value) loadStats()
  if (tab === 'settings' && !settings.value.length) loadSettings()
})
</script>

<style scoped>
.admin-page {}
h1 { color: var(--amber-800); margin-bottom: 1.5rem; }
.tabs { display: flex; gap: 0.25rem; margin-bottom: 1.5rem; border-bottom: 2px solid var(--amber-200); }
.tabs button { padding: 0.5rem 1.25rem; border: none; background: transparent; cursor: pointer; font-size: 0.95rem; border-bottom: 3px solid transparent; margin-bottom: -2px; color: var(--color-text-muted); transition: color 0.15s; }
.tabs button:hover { color: var(--amber-700); }
.tabs button.active { border-bottom-color: var(--amber-600); font-weight: 700; color: var(--amber-800); }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
.meta { font-size: 0.85rem; color: var(--color-text-muted); margin: 0; }
.loading { padding: 2rem; color: var(--color-text-muted); }
.table-wrap { overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px var(--color-card-shadow); }
.table th, .table td { padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--amber-100); font-size: 0.875rem; vertical-align: middle; }
.table th { background: var(--amber-50); font-weight: 700; color: var(--amber-800); }
.table tr:last-child td { border-bottom: none; }
.table tr:hover td { background: var(--amber-50); }
/* Avatar cell */
.avatar-cell { display: flex; align-items: center; justify-content: center; }
.avatar-img { width: 34px; height: 34px; border-radius: 50%; object-fit: cover; border: 1.5px solid var(--amber-200); }
.avatar-initial { width: 34px; height: 34px; border-radius: 50%; background: var(--amber-200); color: var(--amber-800); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.9rem; }
.email-cell { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text-muted); font-size: 0.82rem; }
.role-badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 10px; font-size: 0.75rem; font-weight: 700; }
.role-badge.admin { background: #FEF3C7; color: #92400E; }
.role-badge.teacher { background: #D1FAE5; color: #065F46; }
.role-badge.user { background: #EFF6FF; color: #1E40AF; }
.status-badge { padding: 0.15rem 0.55rem; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }
.status-badge.active { background: #D1FAE5; color: #065F46; }
.status-badge.inactive { background: #FEE2E2; color: #991B1B; }
.actions { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.role-select { padding: 0.25rem 0.5rem; border: 1px solid var(--amber-300); border-radius: 5px; font-size: 0.8rem; background: #fff; color: var(--amber-800); cursor: pointer; }
.role-select:focus { outline: none; border-color: var(--amber-500); }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.8rem; border: 1px solid var(--amber-300); background: var(--amber-50); color: var(--amber-800); border-radius: 5px; cursor: pointer; font-weight: 600; white-space: nowrap; }
.btn-sm:hover { background: var(--amber-100); }
.btn-sm.danger { background: #FEF2F2; color: #991B1B; border-color: #FECACA; }
.btn-sm.danger:hover { background: #FEE2E2; }
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-secondary:hover { background: var(--amber-200); }
.pagination { display: flex; align-items: center; gap: 0.75rem; margin-top: 1rem; font-size: 0.875rem; color: var(--color-text-muted); }
.pagination button { padding: 0.3rem 0.8rem; border: 1px solid var(--amber-300); background: #fff; border-radius: 5px; cursor: pointer; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1.25rem; }
.stat-card { background: #fff; border: 1.5px solid var(--amber-200); border-radius: 12px; padding: 1.75rem; text-align: center; box-shadow: 0 1px 4px var(--color-card-shadow); }
.stat-val { font-size: 2.8rem; font-weight: 800; color: var(--amber-700); line-height: 1; }
.stat-lbl { color: var(--color-text-muted); font-size: 0.9rem; margin-top: 0.4rem; }
.settings-list { max-width: 600px; }
.setting-row { display: flex; align-items: center; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid var(--amber-100); }
.setting-row label { width: 220px; font-family: monospace; font-size: 0.875rem; color: var(--amber-800); flex-shrink: 0; }
.form-input { width: 100%; padding: 0.4rem 0.6rem; border: 1px solid var(--amber-300); border-radius: 5px; font-size: 0.9rem; }
.form-input:focus { outline: none; border-color: var(--amber-500); }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 500; }
.modal { background: #fff; border-radius: 14px; padding: 2rem; width: 100%; max-width: 480px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal h2 { color: var(--amber-800); margin: 0 0 1.5rem; font-size: 1.15rem; }
.field { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem; }
.field > label { font-size: 0.875rem; font-weight: 600; color: var(--amber-800); }
.required { color: #DC2626; }
/* Hierarchical role radios */
.role-radios { display: flex; flex-direction: column; gap: 0.5rem; }
.radio-label { display: flex; align-items: flex-start; gap: 0.6rem; padding: 0.6rem 0.75rem; border: 1.5px solid var(--amber-200); border-radius: 8px; cursor: pointer; transition: border-color 0.15s; }
.radio-label:has(input:checked) { border-color: var(--amber-500); background: var(--amber-50); }
.radio-label input[type="radio"] { margin-top: 3px; accent-color: var(--amber-600); }
.radio-text { display: flex; flex-direction: column; gap: 0.1rem; }
.radio-text strong { font-size: 0.875rem; color: var(--amber-900); }
.radio-text small { font-size: 0.78rem; color: var(--color-text-muted); }
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem; }
.alert-error { background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; border-radius: 6px; padding: 0.55rem 0.9rem; font-size: 0.875rem; margin-bottom: 0.75rem; }
.alert-success { background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0; border-radius: 6px; padding: 0.55rem 0.9rem; font-size: 0.875rem; margin-bottom: 0.75rem; }
</style>
