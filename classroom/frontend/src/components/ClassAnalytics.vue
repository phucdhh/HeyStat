<template>
  <div class="analytics">
    <div v-if="loading" class="empty">Đang tính phân tích…</div>
    <template v-else-if="data">
      <div class="stats">
        <div class="stat">
          <span class="v">{{ data.engagement.students_submitted }}/{{ data.engagement.students }}</span>
          <span class="l">học viên đã nộp bài</span>
        </div>
        <div class="stat">
          <span class="v">{{ pct(data.engagement.submitted_rate) }}</span>
          <span class="l">tỉ lệ nộp</span>
        </div>
        <div class="stat">
          <span class="v">{{ data.engagement.average_score ?? '—' }}</span>
          <span class="l">điểm trung bình</span>
        </div>
        <div class="stat">
          <span class="v">{{ data.engagement.final_submissions }}/{{ data.engagement.assignments }}</span>
          <span class="l">bài nộp / bài tập</span>
        </div>
        <div class="stat">
          <span class="v">{{ data.engagement.draft_snapshots }}</span>
          <span class="l">lần đồng bộ kết quả</span>
        </div>
      </div>

      <h3>Khái niệm học viên hay sai nhất</h3>
      <div v-if="!data.misconceptions.length" class="empty">
        Chưa có lỗi nào được ghi nhận – cần cấu hình tiêu chí chấm cho bài tập.
      </div>
      <div v-else class="mis">
        <div v-for="(m, i) in data.misconceptions" :key="i" class="mis-row">
          <span class="count">{{ m.count }}×</span>
          <div>
            <strong>{{ m.label }}</strong>
            <p>{{ m.explanation }}</p>
          </div>
        </div>
      </div>

      <h3>Độ chính xác theo kĩ năng</h3>
      <div v-if="!data.skills.length" class="empty">Chưa có dữ liệu.</div>
      <div v-else class="skills">
        <div v-for="s in data.skills" :key="s.skill" class="skill">
          <div class="skill-head">
            <span>{{ s.label }}</span>
            <span class="muted">{{ s.attempts }} lượt · {{ pct(s.accuracy) }}</span>
          </div>
          <div class="bar"><div class="fill" :style="{ width: pct(s.accuracy) }" /></div>
        </div>
      </div>
    </template>
    <p v-else class="empty">Không load được phân tích.</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '@/api/client'

const props = defineProps<{ classId: string }>()

const data = ref<any>(null)
const loading = ref(true)

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`

onMounted(async () => {
  try {
    const { data: d } = await api.get(`/classes/${props.classId}/analytics`)
    data.value = d
  } finally { loading.value = false }
})
</script>

<style scoped>
.stats { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.25rem; }
.stat { background: #fff; border: 1.5px solid var(--amber-200); border-radius: 10px; padding: 0.7rem 1rem; min-width: 8rem; }
.stat .v { display: block; font-size: 1.35rem; font-weight: 800; color: var(--amber-800); }
.stat .l { font-size: 0.75rem; color: var(--color-text-muted); }
h3 { color: var(--amber-800); font-size: 0.95rem; margin: 1.25rem 0 0.5rem; }
.mis-row { display: flex; gap: 0.7rem; padding: 0.5rem 0; border-bottom: 1px solid var(--amber-100); }
.mis-row strong { font-size: 0.87rem; color: #B91C1C; }
.mis-row p { margin: 0.15rem 0 0; font-size: 0.8rem; color: var(--color-text-muted); }
.count { font-weight: 800; color: #B91C1C; min-width: 2.6rem; }
.skill { margin-bottom: 0.6rem; max-width: 34rem; }
.skill-head { display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.2rem; }
.bar { height: 7px; background: var(--amber-100); border-radius: 4px; overflow: hidden; }
.fill { height: 100%; background: var(--amber-500); }
.muted, .empty { color: var(--color-text-muted); font-size: 0.82rem; }
</style>
