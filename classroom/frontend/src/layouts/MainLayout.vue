<template>
  <div class="layout">
    <nav class="sidebar">
      <div class="logo">📊 HeyStat</div>

      <div class="nav-section">
        <RouterLink to="/" class="nav-link">
          <span class="nav-icon">🏠</span> Tổng quan
        </RouterLink>
        <RouterLink to="/classes" class="nav-link">
          <span class="nav-icon">📚</span> Lớp học
        </RouterLink>
        <RouterLink to="/files" class="nav-link">
          <span class="nav-icon">📁</span> Tệp của tôi
        </RouterLink>
        <a href="/" target="_blank" class="nav-link heystat-link">
          <span class="nav-icon">📊</span> Mở HeyStat
          <span class="ext-icon">↗</span>
        </a>
        <RouterLink v-if="auth.isTeacher" to="/teacher" class="nav-link">
          <span class="nav-icon">🎓</span> Quản lý lớp
        </RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/admin" class="nav-link">
          <span class="nav-icon">⚙️</span> Quản trị
        </RouterLink>
      </div>

      <div class="spacer" />

      <div class="nav-section nav-bottom">
        <!-- Notification bell -->
        <button class="nav-link notif-btn" @click="toggleNotif">
          <span class="nav-icon">🔔</span>
          Thông báo
          <span v-if="notifStore.unread > 0" class="badge">{{ notifStore.unread }}</span>
        </button>

        <!-- Profile link -->
        <RouterLink to="/profile" class="nav-link">
          <span class="nav-icon">👤</span> Thông tin cá nhân
        </RouterLink>

        <!-- User info -->
        <div class="user-info">
          <div class="avatar-circle">
            <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" alt="Avatar" class="avatar-img" />
            <template v-else>{{ initials }}</template>
          </div>
          <div class="user-name">{{ auth.user?.full_name || auth.user?.email }}</div>
        </div>

        <button class="logout-btn" @click="handleLogout">Đăng xuất</button>
      </div>
    </nav>

    <main class="content">
      <RouterView />
    </main>

    <!-- Notification panel -->
    <div v-if="showNotif" class="notif-panel">
      <div class="notif-header">
        <strong>Thông báo</strong>
        <div class="notif-actions">
          <button class="btn-text" @click="notifStore.markAllRead()">Đọc tất cả</button>
          <button class="btn-text" @click="showNotif = false">✕</button>
        </div>
      </div>
      <div v-if="notifStore.items.length === 0" class="notif-empty">Không có thông báo</div>
      <div
        v-for="n in notifStore.items"
        :key="n.id"
        class="notif-item"
        :class="{ unread: !n.is_read }"
        @click="notifStore.markRead(n.id)"
      >
        {{ n.message }}
        <div class="notif-time">{{ formatTime(n.created_at) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotifStore } from '@/stores/notifications'

const auth = useAuthStore()
const notifStore = useNotifStore()
const router = useRouter()
const showNotif = ref(false)

onMounted(() => notifStore.fetch())

const initials = computed(() => {
  const name = auth.user?.full_name || auth.user?.email || ''
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
})

function toggleNotif() {
  showNotif.value = !showNotif.value
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return ''
  }
}
</script>

<style scoped>
.layout { display: flex; min-height: 100vh; }

/* ── Sidebar ──────────────────────────────────────────── */
.sidebar {
  width: 230px;
  background: linear-gradient(180deg, #92400E 0%, #7C2D12 100%);
  color: var(--amber-100);
  display: flex;
  flex-direction: column;
  padding: 1rem 0.75rem;
  gap: 0.25rem;
  position: fixed;
  top: 0; left: 0; bottom: 0;
  z-index: 100;
  overflow-y: auto;
  border-right: 1px solid rgba(251,191,36,0.15);
}

.logo {
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--amber-300);
  padding: 0.4rem 0.5rem 1rem;
  letter-spacing: 0.02em;
  border-bottom: 1px solid rgba(251,191,36,0.2);
  margin-bottom: 0.5rem;
}

.nav-section { display: flex; flex-direction: column; gap: 0.15rem; }

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--amber-200);
  text-decoration: none;
  padding: 0.5rem 0.65rem;
  border-radius: 7px;
  font-size: 0.9rem;
  font-weight: 500;
  transition: background 0.15s, color 0.15s;
  cursor: pointer;
  border: none;
  background: transparent;
  width: 100%;
  text-align: left;
}
.nav-link:hover {
  background: rgba(251,191,36,0.15);
  color: var(--amber-100);
}
.nav-link.router-link-exact-active,
.nav-link.router-link-active:not([href="/profile"]) {
  background: rgba(251,191,36,0.28);
  color: var(--amber-300);
  font-weight: 700;
}

.nav-icon { font-size: 1rem; flex-shrink: 0; }

.spacer { flex: 1; }
.nav-bottom { padding-top: 0.5rem; border-top: 1px solid rgba(251,191,36,0.2); gap: 0.2rem; }

/* Notification */
.notif-btn { position: relative; }
.badge {
  margin-left: auto;
  background: #DC2626;
  color: #fff;
  border-radius: 10px;
  padding: 0 6px;
  font-size: 0.7rem;
  font-weight: 700;
  line-height: 1.4;
}

/* User info block */
.user-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.65rem;
  background: rgba(0,0,0,0.15);
  border-radius: 7px;
  margin: 0.25rem 0;
}
.avatar-circle {
  width: 32px; height: 32px;
  background: var(--amber-500);
  color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  flex-shrink: 0;
  overflow: hidden;
}
.avatar-img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
.user-name {
  font-size: 0.8rem;
  color: var(--amber-200);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ext-icon { margin-left: auto; font-size: 0.8rem; opacity: 0.7; }
.heystat-link { border: 1px solid rgba(251,191,36,0.3); }
.heystat-link:hover { border-color: rgba(251,191,36,0.6); background: rgba(251,191,36,0.2); }

.logout-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(220,38,38,0.85);
  border: none;
  color: #fff;
  padding: 0.5rem 0.65rem;
  border-radius: 7px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  width: 100%;
  transition: background 0.15s;
}
.logout-btn::before { content: '🚪'; }
.logout-btn:hover { background: rgba(220,38,38,1); }

/* ── Main content ──────────────────────────────────────── */
.content {
  margin-left: 230px;
  padding: 2rem 2.5rem;
  flex: 1;
  min-height: 100vh;
  background: var(--color-page-bg);
}

/* ── Notification panel ────────────────────────────────── */
.notif-panel {
  position: fixed;
  top: 0; right: 0;
  width: 340px; height: 100vh;
  background: #fff;
  box-shadow: -4px 0 20px rgba(0,0,0,0.12);
  display: flex; flex-direction: column;
  z-index: 200;
}
.notif-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 2px solid var(--amber-100);
  background: var(--amber-50);
}
.notif-actions { display: flex; gap: 0.5rem; align-items: center; }
.btn-text {
  background: none; border: none; cursor: pointer;
  color: var(--amber-700); font-size: 0.85rem;
  padding: 0.25rem 0.4rem; border-radius: 4px;
}
.btn-text:hover { background: var(--amber-100); }
.notif-item {
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--amber-100);
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.1s;
}
.notif-item:hover { background: var(--amber-50); }
.notif-item.unread { background: #FFFBEB; font-weight: 600; border-left: 3px solid var(--amber-500); }
.notif-time { font-size: 0.75rem; color: var(--color-text-muted); margin-top: 0.2rem; }
.notif-empty { padding: 1.5rem; color: var(--color-text-muted); text-align: center; }
</style>

