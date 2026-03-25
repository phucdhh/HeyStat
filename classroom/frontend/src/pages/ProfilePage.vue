<template>
  <div class="profile-page">
    <h1>Thông tin cá nhân</h1>

    <!-- Avatar section -->
    <div class="section card">
      <h2>Ảnh đại diện</h2>
      <div class="avatar-area">
        <div class="avatar-preview">
          <img v-if="avatarPreview || auth.user?.avatar_url"
               :src="(avatarPreview || auth.user?.avatar_url) ?? undefined"
               alt="Avatar" class="avatar-img" />
          <div v-else class="avatar-initials">{{ initials }}</div>
        </div>
        <div class="avatar-upload">
          <label class="btn-secondary" style="cursor:pointer;">
            📷 Chọn ảnh
            <input type="file" accept="image/jpeg,image/png,image/webp,image/gif"
                   style="display:none" @change="onAvatarSelected" />
          </label>
          <p class="hint">PNG, JPG, WebP, GIF · Tối đa 2MB</p>
          <button v-if="avatarFile" class="btn-primary" :disabled="savingAvatar" @click="uploadAvatar">
            {{ savingAvatar ? 'Đang tải…' : 'Lưu ảnh' }}
          </button>
          <div v-if="avatarError" class="alert-error" style="margin-top:0.5rem;">{{ avatarError }}</div>
          <div v-if="avatarOk" class="alert-success" style="margin-top:0.5rem;">Cập nhật ảnh thành công!</div>
        </div>
      </div>
    </div>

    <!-- Basic info -->
    <div class="section card">
      <h2>Thông tin cơ bản</h2>
      <form @submit.prevent="saveProfile">
        <div class="field">
          <label>Email</label>
          <input type="email" class="form-input" :value="auth.user?.email" disabled />
        </div>
        <div class="field">
          <label>Họ và tên</label>
          <input type="text" class="form-input" v-model="form.full_name" required placeholder="Nhập họ tên" />
        </div>
        <div class="field">
          <label>Số điện thoại</label>
          <input type="tel" class="form-input" v-model="form.phone" placeholder="VD: 0912345678" />
        </div>
        <div v-if="profileError" class="alert-error">{{ profileError }}</div>
        <div v-if="profileOk" class="alert-success">Cập nhật thông tin thành công!</div>
        <div class="form-actions">
          <button type="submit" class="btn-primary" :disabled="savingProfile">
            {{ savingProfile ? 'Đang lưu…' : 'Lưu thay đổi' }}
          </button>
        </div>
      </form>
    </div>

    <!-- Change password -->
    <div class="section card">
      <h2>Đổi mật khẩu</h2>
      <form @submit.prevent="changePassword">
        <div class="field">
          <label>Mật khẩu hiện tại</label>
          <input type="password" class="form-input" v-model="pwForm.current" required autocomplete="current-password" />
        </div>
        <div class="field">
          <label>Mật khẩu mới</label>
          <input type="password" class="form-input" v-model="pwForm.new_password" required
                 placeholder="Tối thiểu 8 ký tự, có chữ và số" autocomplete="new-password" />
        </div>
        <div class="field">
          <label>Xác nhận mật khẩu mới</label>
          <input type="password" class="form-input" v-model="pwForm.confirm" required autocomplete="new-password" />
        </div>
        <div v-if="pwError" class="alert-error">{{ pwError }}</div>
        <div v-if="pwOk" class="alert-success">Đổi mật khẩu thành công!</div>
        <div class="form-actions">
          <button type="submit" class="btn-primary" :disabled="savingPw">
            {{ savingPw ? 'Đang lưu…' : 'Đổi mật khẩu' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'

const auth = useAuthStore()

// ── Avatar ────────────────────────────────────────────────
const avatarFile = ref<File | null>(null)
const avatarPreview = ref<string | null>(null)
const savingAvatar = ref(false)
const avatarError = ref('')
const avatarOk = ref(false)

function onAvatarSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  avatarFile.value = file
  avatarPreview.value = URL.createObjectURL(file)
  avatarError.value = ''
  avatarOk.value = false
}

async function uploadAvatar() {
  if (!avatarFile.value) return
  savingAvatar.value = true
  avatarError.value = ''
  avatarOk.value = false
  try {
    const fd = new FormData()
    fd.append('file', avatarFile.value)
    const { data } = await api.post('/auth/avatar', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    auth.user = { ...auth.user!, avatar_url: data.avatar_url }
    avatarFile.value = null
    avatarOk.value = true
  } catch (err: any) {
    avatarError.value = err.response?.data?.detail || 'Tải ảnh thất bại'
  } finally {
    savingAvatar.value = false
  }
}

// ── Profile info ──────────────────────────────────────────
const form = ref({
  full_name: auth.user?.full_name || '',
  phone: auth.user?.phone || '',
})
const savingProfile = ref(false)
const profileError = ref('')
const profileOk = ref(false)

async function saveProfile() {
  savingProfile.value = true
  profileError.value = ''
  profileOk.value = false
  try {
    const { data } = await api.patch('/auth/profile', {
      full_name: form.value.full_name,
      phone: form.value.phone || null,
    })
    auth.user = { ...auth.user!, full_name: data.full_name, phone: data.phone }
    profileOk.value = true
  } catch (err: any) {
    const detail = err.response?.data?.detail
    profileError.value = Array.isArray(detail)
      ? detail.map((d: any) => d.msg).join(', ')
      : detail || 'Cập nhật thất bại'
  } finally {
    savingProfile.value = false
  }
}

// ── Change password ─────────────────────────────────────
const pwForm = ref({ current: '', new_password: '', confirm: '' })
const savingPw = ref(false)
const pwError = ref('')
const pwOk = ref(false)

async function changePassword() {
  pwError.value = ''
  pwOk.value = false
  if (pwForm.value.new_password !== pwForm.value.confirm) {
    pwError.value = 'Mật khẩu xác nhận không khớp'
    return
  }
  savingPw.value = true
  try {
    await api.post('/auth/change-password', {
      current_password: pwForm.value.current,
      new_password: pwForm.value.new_password,
    })
    pwForm.value = { current: '', new_password: '', confirm: '' }
    pwOk.value = true
  } catch (err: any) {
    const detail = err.response?.data?.detail
    pwError.value = Array.isArray(detail)
      ? detail.map((d: any) => d.msg).join(', ')
      : detail || 'Đổi mật khẩu thất bại'
  } finally {
    savingPw.value = false
  }
}

// ── Helpers ──────────────────────────────────────────────
const initials = computed(() => {
  const name = auth.user?.full_name || auth.user?.email || ''
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
})
</script>

<style scoped>
.profile-page { max-width: 640px; }
h1 { color: var(--amber-800); margin-bottom: 1.5rem; }
h2 { font-size: 1.05rem; color: var(--amber-700); margin: 0 0 1.25rem; border-bottom: 1px solid var(--amber-100); padding-bottom: 0.5rem; }

.section { margin-bottom: 1.5rem; }
.card {
  background: #fff;
  border: 1px solid var(--amber-200);
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 1px 4px var(--color-card-shadow);
}

/* Avatar */
.avatar-area { display: flex; align-items: flex-start; gap: 1.5rem; flex-wrap: wrap; }
.avatar-preview { flex-shrink: 0; }
.avatar-img {
  width: 96px; height: 96px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid var(--amber-300);
}
.avatar-initials {
  width: 96px; height: 96px;
  border-radius: 50%;
  background: var(--amber-500);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 2rem; font-weight: 700;
  border: 3px solid var(--amber-300);
}
.avatar-upload { display: flex; flex-direction: column; gap: 0.5rem; }
.hint { font-size: 0.8rem; color: var(--color-text-muted); margin: 0; }

/* Form */
.field { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem; }
.field label { font-size: 0.875rem; font-weight: 600; color: var(--amber-800); }
.form-actions { margin-top: 1rem; }

.btn-primary {
  background: var(--color-primary);
  color: #fff; border: none;
  padding: 0.55rem 1.4rem; border-radius: 7px;
  cursor: pointer; font-size: 0.95rem; font-weight: 600;
  transition: background 0.15s;
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-secondary {
  display: inline-block;
  background: var(--amber-100); color: var(--amber-800);
  border: 1px solid var(--amber-300);
  padding: 0.5rem 1rem; border-radius: 7px;
  font-size: 0.9rem; font-weight: 600;
}
.btn-secondary:hover { background: var(--amber-200); }

.alert-error {
  background: #FEF2F2; color: #991B1B;
  border: 1px solid #FECACA; border-radius: 6px;
  padding: 0.55rem 0.9rem; font-size: 0.875rem;
}
.alert-success {
  background: #F0FDF4; color: #166534;
  border: 1px solid #BBF7D0; border-radius: 6px;
  padding: 0.55rem 0.9rem; font-size: 0.875rem;
}
</style>
