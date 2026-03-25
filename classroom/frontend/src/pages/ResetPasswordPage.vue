<template>
  <div class="auth-page">
    <h1>Đặt lại mật khẩu</h1>
    <form @submit.prevent="submit">
      <label>Mật khẩu mới <input v-model="password" type="password" required /></label>
      <label>Xác nhận <input v-model="confirm" type="password" required /></label>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="success" class="success">{{ success }}</p>
      <button type="submit" :disabled="loading">Đặt lại</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/client'

const route = useRoute()
const router = useRouter()
const password = ref('')
const confirm = ref('')
const error = ref('')
const success = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''; success.value = ''
  if (password.value !== confirm.value) { error.value = 'Mật khẩu không khớp'; return }
  loading.value = true
  try {
    await api.post('/auth/reset-password', { token: route.query.token, new_password: password.value })
    success.value = 'Đổi mật khẩu thành công! Đang chuyển hướng…'
    setTimeout(() => router.push('/login'), 2000)
  } catch (e: any) { error.value = e?.response?.data?.detail ?? 'Token không hợp lệ hoặc đã hết hạn' }
  finally { loading.value = false }
}
</script>

<style scoped>
.auth-page { max-width: 400px; margin: 10vh auto; padding: 2rem; background: #fff; border-radius: 8px; box-shadow: 0 2px 16px rgba(0,0,0,0.1); }
h1 { text-align: center; margin-bottom: 1.5rem; }
form { display: flex; flex-direction: column; gap: 0.8rem; }
label { display: flex; flex-direction: column; font-size: 0.9rem; gap: 0.3rem; }
input { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
button { padding: 0.7rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.error { color: red; } .success { color: green; }
</style>
