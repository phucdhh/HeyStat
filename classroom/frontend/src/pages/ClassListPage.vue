<template>
  <div class="class-list-page">
    <div class="page-header">
      <h1>Lớp học</h1>
      <button v-if="auth.isTeacher" class="btn-secondary" @click="showCreate = true">+ Tạo lớp mới</button>
      <button class="btn-primary" @click="showJoin = true">+ Tham gia lớp</button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="!classes.length" class="empty">Bạn chưa tham gia lớp nào.</div>
    <div v-else class="grid">
      <RouterLink v-for="cls in classes" :key="cls.id" :to="`/classes/${cls.id}`" class="class-card">
        <div class="cls-title">{{ cls.title }}</div>
        <div class="cls-desc">{{ cls.description }}</div>
        <div class="cls-teacher">👤 {{ cls.teacher_name }}</div>
      </RouterLink>
    </div>

    <!-- Join modal -->
    <div v-if="showJoin" class="modal-overlay" @click.self="showJoin = false">
      <div class="modal">
        <h2>Tham gia lớp học</h2>
        <div class="field">
          <label>Mã lớp <span class="req">*</span></label>
          <input class="form-input" v-model="joinKey" placeholder="VD: AB3X9K2W"
                 @keyup.enter="joinClass" autofocus />
        </div>
        <p v-if="joinError" class="error">{{ joinError }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showJoin = false">Huỷ</button>
          <button class="btn-primary" :disabled="joining" @click="joinClass">
            {{ joining ? 'Đang tham gia…' : 'Tham gia' }}
          </button>
        </div>
      </div>
    </div>
    <ClassCreateModal :show="showCreate" @close="showCreate = false" @created="load" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import ClassCreateModal from '@/components/ClassCreateModal.vue'

const auth = useAuthStore()
const classes = ref<any[]>([])
const loading = ref(true)

const showJoin = ref(false)
const showCreate = ref(false)
const joinKey = ref('')
const joinError = ref('')
const joining = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/classes')
    classes.value = data
  } finally { loading.value = false }
}

async function joinClass() {
  joinError.value = ''
  if (!joinKey.value.trim()) { joinError.value = 'Vui lòng nhập mã lớp'; return }
  joining.value = true
  try {
    await api.post('/classes/join', { enrollment_key: joinKey.value.trim() })
    joinKey.value = ''
    showJoin.value = false
    await load()
  } catch (e: any) {
    joinError.value = e?.response?.data?.detail ?? 'Không thể tham gia lớp'
  } finally { joining.value = false }
}

onMounted(load)
</script>

<style scoped>
.class-list-page {}
.page-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.5rem; }
.page-header h1 { flex: 1; margin: 0; color: var(--amber-800); }
.loading { color: var(--color-text-muted); padding: 2rem 0; }
.empty { color: var(--color-text-muted); padding: 2rem 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1rem; }
.class-card { background: #fff; border: 1.5px solid var(--amber-200); border-radius: 12px; padding: 1.2rem; text-decoration: none; color: inherit; display: block; transition: box-shadow 0.15s, border-color 0.15s; }
.class-card:hover { box-shadow: 0 4px 16px rgba(146,64,14,0.12); border-color: var(--amber-400); }
.cls-title { font-weight: 700; font-size: 1rem; color: var(--amber-900); margin-bottom: 0.3rem; }
.cls-desc { font-size: 0.85rem; color: var(--color-text-muted); margin-bottom: 0.5rem; line-height: 1.4; }
.cls-teacher { font-size: 0.8rem; color: var(--amber-700); font-weight: 600; }
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: var(--amber-100); color: var(--amber-800); border: 1px solid var(--amber-300); padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 500; }
.modal { background: #fff; border-radius: 14px; padding: 2rem; width: 100%; max-width: 400px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal h2 { color: var(--amber-800); margin: 0 0 1.25rem; font-size: 1.1rem; font-weight: 700; }
.field { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem; }
.field > label { font-size: 0.875rem; font-weight: 600; color: var(--amber-800); }
.req { color: #DC2626; }
.form-input { padding: 0.5rem 0.7rem; border: 1.5px solid var(--amber-300); border-radius: 7px; font-size: 1rem; letter-spacing: 0.06em; }
.form-input:focus { outline: none; border-color: var(--amber-500); }
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; }
.error { color: #DC2626; font-size: 0.85rem; background: #FEF2F2; border: 1px solid #FECACA; padding: 0.4rem 0.6rem; border-radius: 6px; margin: 0; }
</style>
