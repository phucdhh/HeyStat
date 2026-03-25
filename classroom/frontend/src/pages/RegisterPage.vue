<template>
  <div class="auth-page">
    <h1>Tạo tài khoản</h1>
    <form @submit.prevent="submit">
      <label>Email <input v-model="form.email" type="email" required /></label>
      <label>Họ và tên <input v-model="form.full_name" required /></label>
      <label>Mật khẩu <input v-model="form.password" type="password" required /></label>
      <label>Xác nhận mật khẩu <input v-model="form.confirm" type="password" required /></label>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="success" class="success">{{ success }}</p>
      <button type="submit" :disabled="loading">{{ loading ? 'Đang tạo…' : 'Tạo tài khoản' }}</button>
      <div class="links"><RouterLink to="/login">Đã có tài khoản? Đăng nhập</RouterLink></div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import api from '@/api/client'

const form = reactive({ email: '', full_name: '', password: '', confirm: '' })
const error = ref('')
const success = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  success.value = ''
  if (form.password !== form.confirm) { error.value = 'Mật khẩu không khớp'; return }
  loading.value = true
  try {
    await api.post('/auth/register', { email: form.email, full_name: form.full_name, password: form.password })
    success.value = 'Tạo tài khoản thành công! Bạn có thể đăng nhập ngay.'
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Đăng ký thất bại'
  } finally { loading.value = false }
}
</script>

<style scoped>
.auth-page { max-width: 420px; margin: 8vh auto; padding: 2.25rem; background: #fff; border-radius: 14px; box-shadow: 0 4px 24px rgba(146,64,14,0.12); border: 1.5px solid var(--amber-200); }
h1 { text-align: center; margin-bottom: 1.5rem; color: var(--amber-800); font-size: 1.4rem; font-weight: 800; }
form { display: flex; flex-direction: column; gap: 0.85rem; }
label { display: flex; flex-direction: column; font-size: 0.875rem; gap: 0.3rem; font-weight: 600; color: var(--amber-800); }
input { padding: 0.55rem 0.7rem; border: 1.5px solid var(--amber-300); border-radius: 7px; font-size: 0.95rem; transition: border-color 0.15s; }
input:focus { outline: none; border-color: var(--amber-500); box-shadow: 0 0 0 3px rgba(245,158,11,0.12); }
button { padding: 0.75rem; background: var(--color-primary); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; font-weight: 700; transition: background 0.15s; margin-top: 0.25rem; }
button:hover { background: var(--color-primary-hover); }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.45rem 0.7rem; border-radius: 6px; }
.success { color: #166534; font-size: 0.85rem; background: #F0FDF4; border: 1px solid #BBF7D0; padding: 0.45rem 0.7rem; border-radius: 6px; }
.links { text-align: center; font-size: 0.875rem; color: var(--color-text-muted); }
.links a { color: var(--amber-700); font-weight: 600; text-decoration: none; }
.links a:hover { color: var(--amber-900); text-decoration: underline; }
</style>
