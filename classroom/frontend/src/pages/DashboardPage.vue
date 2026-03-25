<template>
  <div>
    <h1 style="color: var(--amber-800); margin-bottom: 0.25rem;">Tổng quan</h1>
    <p v-if="auth.user" style="color: var(--color-text-muted); margin-bottom: 2rem;">
      Xin chào, <strong style="color: var(--color-text);">{{ auth.user.full_name || auth.user.email }}</strong>!
    </p>
    <div class="cards">
      <RouterLink to="/classes" class="card">
        <div class="card-icon">📚</div>
        <div class="card-label">Lớp học của tôi</div>
      </RouterLink>
      <RouterLink to="/files" class="card">
        <div class="card-icon">📁</div>
        <div class="card-label">Tệp của tôi</div>
      </RouterLink>
      <RouterLink v-if="auth.isTeacher" to="/teacher" class="card">
        <div class="card-icon">🎓</div>
        <div class="card-label">Quản lý lớp</div>
      </RouterLink>
      <RouterLink to="/profile" class="card">
        <div class="card-icon">👤</div>
        <div class="card-label">Thông tin cá nhân</div>
      </RouterLink>
      <a href="/" target="_blank" class="card heystat-card">
        <div class="card-icon">📊</div>
        <div class="card-label">Mở HeyStat <span style="font-size:0.75rem;">↗</span></div>
        <div class="card-hint">Phân tích & vẽ biểu đồ</div>
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
</script>

<style scoped>
.cards { display: flex; gap: 1.25rem; flex-wrap: wrap; }
.card {
  background: #fff;
  border: 1.5px solid var(--amber-200);
  border-radius: 12px;
  padding: 1.75rem 2rem;
  text-align: center;
  text-decoration: none;
  color: var(--color-text);
  min-width: 150px;
  transition: box-shadow 0.2s, transform 0.15s, border-color 0.15s;
}
.card:hover {
  box-shadow: 0 6px 20px rgba(217,119,6,0.15);
  transform: translateY(-3px);
  border-color: var(--amber-400);
}
.card-icon { font-size: 2.25rem; margin-bottom: 0.6rem; }
.card-label { font-weight: 600; font-size: 0.95rem; color: var(--amber-800); }
.card-hint { font-size: 0.78rem; color: var(--color-text-muted); margin-top: 0.2rem; }
.heystat-card { border-color: var(--amber-400); background: linear-gradient(135deg, #fff 60%, #FFFBEB); }
.heystat-card:hover { border-color: var(--amber-600); }
</style>

