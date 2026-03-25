<template>
  <div class="auth-page">
    <h1>Quên mật khẩu</h1>
    <form @submit.prevent="submit">
      <label>Email <input v-model="email" type="email" required /></label>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="success" class="success">{{ success }}</p>
      <button type="submit" :disabled="loading">Gửi link đặt lại</button>
      <div class="links"><RouterLink to="/login">Quay lại đăng nhập</RouterLink></div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import api from '@/api/client'

const email = ref('')
const error = ref('')
const success = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''; success.value = ''; loading.value = true
  try {
    await api.post('/auth/forgot-password', { email: email.value })
    success.value = 'Nếu email tồn tại, link đặt lại đã được gửi.'
  } catch { error.value = 'Có lỗi xảy ra' } finally { loading.value = false }
}
</script>

<style scoped>
.auth-page { max-width: 400px; margin: 10vh auto; padding: 2rem; background: #fff; border-radius: 8px; box-shadow: 0 2px 16px rgba(0,0,0,0.1); }
h1 { text-align: center; margin-bottom: 1.5rem; }
form { display: flex; flex-direction: column; gap: 0.8rem; }
label { display: flex; flex-direction: column; font-size: 0.9rem; gap: 0.3rem; }
input { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; }
button { padding: 0.7rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.error { color: red; } .success { color: green; }
.links { text-align: center; font-size: 0.85rem; }
</style>
