<template>
  <div>
    <div v-if="loading">Đang tải…</div>
    <div v-else-if="cls">
      <div class="header">
        <div>
          <h1>{{ cls.name }}</h1>
          <p class="sub">{{ cls.description }}</p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">{{ tab.label }}</button>
      </div>

      <!-- Assignments tab -->
      <div v-if="activeTab === 'assignments'">
        <div v-if="assignments.length === 0" class="empty">Chưa có bài tập.</div>
        <div v-for="a in assignments" :key="a.id" class="list-item">
          <RouterLink :to="`/classes/${classId}/assignments/${a.id}`">{{ a.title }}</RouterLink>
          <span class="meta">Hạn: {{ a.deadline ? new Date(a.deadline).toLocaleString('vi-VN') : 'Không có' }}</span>
        </div>
      </div>

      <!-- Lessons tab -->
      <div v-if="activeTab === 'lessons'">
        <div v-if="lessons.length === 0" class="empty">Chưa có bài học.</div>
        <div v-for="l in lessons" :key="l.id" class="list-item">
          <RouterLink :to="`/classes/${classId}/lessons/${l.id}`">{{ l.title }}</RouterLink>
        </div>
      </div>

      <!-- Quizzes tab -->
      <div v-if="activeTab === 'quizzes'">
        <div class="actions" v-if="auth.isTeacher">
          <RouterLink :to="`/classes/${classId}/quizzes/new`" class="btn">+ Tạo Quiz</RouterLink>
        </div>
        <div v-if="quizzes.length === 0" class="empty">Chưa có quiz.</div>
        <div v-for="q in quizzes" :key="q.id" class="list-item">
          <RouterLink :to="`/classes/${classId}/quizzes/${q.id}`">{{ q.title }}</RouterLink>
          <span class="meta">{{ q.question_count }} câu hỏi</span>
        </div>
      </div>

      <!-- Files tab -->
      <div v-if="activeTab === 'files'">
        <div v-if="files.length === 0" class="empty">Chưa có tệp.</div>
        <div v-for="f in files" :key="f.id" class="list-item">
          <a :href="`/api/v1/classes/${classId}/files/${f.id}/download`" target="_blank">{{ f.filename }}</a>
          <span class="meta">{{ (f.size_bytes / 1024).toFixed(1) }} KB</span>
        </div>
      </div>

      <!-- Members tab (teacher only) -->
      <div v-if="activeTab === 'members' && auth.isTeacher">
        <div v-if="members.length === 0" class="empty">Chưa có học viên.</div>
        <table v-else class="table">
          <thead><tr><th>Tên</th><th>Username</th><th>Email</th></tr></thead>
          <tbody>
            <tr v-for="m in members" :key="m.user_id">
              <td>{{ m.full_name || m.username }}</td>
              <td>{{ m.username }}</td>
              <td>{{ m.email }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const classId = route.params.classId as string

const loading = ref(true)
const cls = ref<any>(null)
const assignments = ref<any[]>([])
const lessons = ref<any[]>([])
const quizzes = ref<any[]>([])
const files = ref<any[]>([])
const members = ref<any[]>([])
const activeTab = ref('assignments')

const tabs = computed(() => {
  const t = [
    { key: 'assignments', label: 'Bài tập' },
    { key: 'lessons', label: 'Bài học' },
    { key: 'quizzes', label: 'Quiz' },
    { key: 'files', label: 'Tệp' },
  ]
  if (auth.isTeacher) t.push({ key: 'members', label: 'Học viên' })
  return t
})

onMounted(async () => {
  loading.value = true
  try {
    const [clsRes, assignRes, lessonRes, quizRes, fileRes] = await Promise.all([
      api.get(`/classes/${classId}`),
      api.get(`/classes/${classId}/assignments`),
      api.get(`/classes/${classId}/lessons`),
      api.get(`/classes/${classId}/quizzes`),
      api.get(`/classes/${classId}/files`),
    ])
    cls.value = clsRes.data
    assignments.value = assignRes.data
    lessons.value = lessonRes.data
    quizzes.value = quizRes.data
    files.value = fileRes.data
    if (auth.isTeacher) {
      const memberRes = await api.get(`/classes/${classId}/students`)
      members.value = memberRes.data
    }
  } finally { loading.value = false }
})
</script>

<style scoped>
.header { display: flex; align-items: flex-start; margin-bottom: 1.5rem; }
.header h1 { margin: 0 0 0.3rem; }
.sub { color: #666; margin: 0; }
.tabs { display: flex; gap: 0.3rem; margin-bottom: 1.5rem; border-bottom: 2px solid #eee; padding-bottom: 0; }
.tabs button { padding: 0.5rem 1rem; border: none; background: transparent; cursor: pointer; font-size: 0.95rem; border-bottom: 3px solid transparent; margin-bottom: -2px; }
.tabs button.active { border-bottom-color: #1a1a2e; font-weight: 700; color: #1a1a2e; }
.list-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; border-bottom: 1px solid #f0f0f0; }
.list-item a { font-weight: 600; text-decoration: none; color: #1a1a2e; }
.meta { color: #888; font-size: 0.85rem; }
.empty { color: #888; padding: 1rem 0; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9rem; }
.table th { background: #f8f8f8; font-weight: 600; }
.actions { margin-bottom: 1rem; }
.btn { display: inline-block; padding: 0.5rem 1rem; background: #1a1a2e; color: #fff; text-decoration: none; border-radius: 4px; font-size: 0.9rem; }
</style>
