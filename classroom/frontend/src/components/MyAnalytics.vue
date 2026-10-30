<template>
  <div class="panel">
    <h2>Tiến độ của bạn</h2>
    <div v-if="loading" class="muted">Đang tải…</div>
    <template v-else-if="data">
      <div class="stats">
        <div class="stat">
          <span class="v">{{ data.assignments_completed }}/{{ data.assignments_total }}</span>
          <span class="l">bài tập đã nộp</span>
        </div>
        <div class="stat">
          <span class="v">{{ data.skills.length }}</span>
          <span class="l">kĩ năng đang theo dõi</span>
        </div>
      </div>

      <h3>Kĩ năng thống kê</h3>
      <div v-if="!data.skills.length" class="muted">
        Chưa có dữ liệu – làm và nộp bài trong HeyStat để theo dõi kĩ năng.
      </div>
      <div v-else class="skills">
        <div v-for="s in data.skills" :key="s.skill" class="skill">
          <div class="skill-head">
            <span>{{ s.label }}</span>
            <span class="muted">{{ s.mastered }}/{{ s.attempts }} bài đạt</span>
          </div>
          <div class="bar"><div class="fill" :style="{ width: pct(s) + '%' }" /></div>
        </div>
      </div>

      <template v-if="data.recent.length">
        <h3>Bài gần đây</h3>
        <div v-for="r in data.recent" :key="r.assignment_id + r.submitted_at" class="recent">
          <RouterLink :to="`/classes/${r.class_id}/assignments/${r.assignment_id}`">{{ r.title }}</RouterLink>
          <span class="muted">{{ fmt(r.submitted_at) }}</span>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '@/api/client'

const data = ref<any>(null)
const loading = ref(true)

const pct = (s: any) => Math.round((s.accuracy ?? 0) * 100)
const fmt = (iso: string) => new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

onMounted(async () => {
  try {
    const { data: d } = await api.get('/analytics/my')
    data.value = d
  } finally { loading.value = false }
})
</script>

<style scoped>
.panel { background: #fff; border: 1.5px solid var(--amber-200); border-radius: 12px; padding: 1.25rem 1.5rem; margin-top: 1.5rem; max-width: 46rem; }
h2 { margin: 0 0 0.75rem; color: var(--amber-800); font-size: 1.05rem; }
h3 { margin: 1.25rem 0 0.5rem; color: var(--amber-800); font-size: 0.92rem; }
.stats { display: flex; gap: 2rem; }
.stat .v { display: block; font-size: 1.5rem; font-weight: 800; color: var(--amber-800); }
.stat .l { font-size: 0.78rem; color: var(--color-text-muted); }
.skill { margin-bottom: 0.6rem; }
.skill-head { display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.2rem; }
.bar { height: 7px; background: var(--amber-100); border-radius: 4px; overflow: hidden; }
.fill { height: 100%; background: var(--amber-500); }
.recent { display: flex; gap: 0.75rem; align-items: baseline; font-size: 0.82rem; padding: 0.3rem 0; border-bottom: 1px solid var(--amber-100); flex-wrap: wrap; }
.recent a { color: var(--amber-700); text-decoration: none; font-weight: 600; }
.muted { color: var(--color-text-muted); font-size: 0.8rem; }
</style>
