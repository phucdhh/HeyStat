<template>
  <div>
    <div class="page-header">
      <h1>Lớp học</h1>
      <button @click="showJoin = true">+ Tham gia lớp</button>
      <button v-if="auth.isTeacher" @click="showCreate = true">+ Tạo lớp</button>
    </div>

    <div v-if="loading">Đang tải…</div>
    <div v-else-if="classes.length === 0" class="empty">Bạn chưa tham gia lớp nào.</div>
    <div v-else class="grid">
      <RouterLink
        v-for="cls in classes" :key="cls.id"
        :to="`/classes/${cls.id}`"
        class="class-card"
      >
        <div class="cls-name">{{ cls.name }}</div>
        <div class="cls-meta">{{ cls.description }}</div>
        <div class="cls-meta">Giáo viên: {{ cls.teacher_name }}</div>
      </RouterLink>
    </div>

    <!-- Join modal -->
    <div v-if="showJoin" class="modal-overlay" @click.self="showJoin = false">
      <div class="modal">
        <h2>Tham gia lớp</h2>
        <label>Mã lớp <input v-model="joinKey" placeholder="ABCD1234" /></label>
        <p v-if="joinError" class="error">{{ joinError }}</p>
        <div class="modal-actions">
          <button @click="joinClass">Tham gia</button>
          <button class="secondary" @click="showJoin = false">Huỷ</button>
        </div>
      </div>
    </div>

    <!-- Create modal (teacher) -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal">
        <h2>Tạo lớp mới</h2>
        <label>Tên lớp <input v-model="newClass.name" required /></label>
        <label>Mô tả <textarea v-model="newClass.description" rows="3" /></label>
        <label>Số học viên tối đa <input v-model.number="newClass.max_students" type="number" /></label>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="modal-actions">
          <button @click="createClass">Tạo</button>
          <button class="secondary" @click="showCreate = false">Huỷ</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const classes = ref<any[]>([])
const loading = ref(true)

const showJoin = ref(false)
const joinKey = ref('')
const joinError = ref('')

const showCreate = ref(false)
const newClass = reactive({ name: '', description: '', max_students: 50 })
const createError = ref('')

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/classes')
    classes.value = data
  } finally { loading.value = false }
}

async function joinClass() {
  joinError.value = ''
  try {
    await api.post('/classes/enroll', { enrollment_key: joinKey.value })
    joinKey.value = ''
    showJoin.value = false
    await load()
  } catch (e: any) { joinError.value = e?.response?.data?.detail ?? 'Không thể tham gia' }
}

async function createClass() {
  createError.value = ''
  try {
    await api.post('/classes', newClass)
    showCreate.value = false
    await load()
  } catch (e: any) { createError.value = e?.response?.data?.detail ?? 'Không thể tạo lớp' }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.5rem; }
.page-header h1 { flex: 1; margin: 0; }
button { padding: 0.5rem 1rem; border: none; border-radius: 4px; background: #1a1a2e; color: #fff; cursor: pointer; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
.class-card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1.2rem; text-decoration: none; color: #333; display: block; }
.class-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.cls-name { font-weight: 700; font-size: 1.05rem; margin-bottom: 0.3rem; }
.cls-meta { font-size: 0.85rem; color: #666; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 500; }
.modal { background: #fff; border-radius: 8px; padding: 2rem; min-width: 320px; display: flex; flex-direction: column; gap: 0.8rem; }
.modal h2 { margin: 0 0 0.5rem; }
label { display: flex; flex-direction: column; font-size: 0.9rem; gap: 0.3rem; }
input, textarea { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
.modal-actions { display: flex; gap: 0.5rem; }
.secondary { background: #eee; color: #333; }
.error { color: red; font-size: 0.85rem; }
.empty { color: #888; }
</style>
