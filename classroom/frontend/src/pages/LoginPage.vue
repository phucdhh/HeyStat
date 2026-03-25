<template>
  <div class="auth-page">
    <h1>HeyStat Classroom</h1>
    <p class="subtitle">Đăng nhập để tiếp tục</p>
    <form @submit.prevent="submit">
      <label>Email
        <input v-model="form.email" type="email" autocomplete="email" required />
      </label>
      <label>Mật khẩu
        <input v-model="form.password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? 'Đang đăng nhập…' : 'Đăng nhập' }}</button>
      <div class="links">
        <RouterLink to="/register">Tạo tài khoản</RouterLink> ·
        <RouterLink to="/forgot-password">Quên mật khẩu?</RouterLink>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const form = reactive({ email: '', password: '' })
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(form.email, form.password)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Đăng nhập thất bại'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page { max-width: 420px; margin: 10vh auto; padding: 2.25rem; background: #fff; border-radius: 14px; box-shadow: 0 4px 24px rgba(146,64,14,0.12); border: 1.5px solid var(--amber-200); }
h1 { text-align: center; margin-bottom: 0.3rem; color: var(--amber-800); font-size: 1.6rem; font-weight: 800; }
.subtitle { text-align: center; color: var(--color-text-muted); font-size: 0.9rem; margin-bottom: 1.5rem; }
form { display: flex; flex-direction: column; gap: 0.85rem; }
label { display: flex; flex-direction: column; font-size: 0.875rem; gap: 0.3rem; font-weight: 600; color: var(--amber-800); }
input { padding: 0.55rem 0.7rem; border: 1.5px solid var(--amber-300); border-radius: 7px; font-size: 0.95rem; transition: border-color 0.15s; }
input:focus { outline: none; border-color: var(--amber-500); box-shadow: 0 0 0 3px rgba(245,158,11,0.12); }
button[type="submit"] { padding: 0.75rem; background: var(--color-primary); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; font-weight: 700; transition: background 0.15s; margin-top: 0.25rem; }
button[type="submit"]:hover { background: var(--color-primary-hover); }
button[type="submit"]:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.45rem 0.7rem; border-radius: 6px; }
.links { text-align: center; font-size: 0.875rem; color: var(--color-text-muted); }
.links a { color: var(--amber-700); font-weight: 600; text-decoration: none; }
.links a:hover { color: var(--amber-900); text-decoration: underline; }
</style>
