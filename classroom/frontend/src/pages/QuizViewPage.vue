<template>
  <div>
    <RouterLink :to="`/classes/${classId}`" class="back">← Quay lại lớp</RouterLink>

    <!-- Not started state -->
    <div v-if="!attempt">
      <h1>{{ quiz?.title }}</h1>
      <div class="markdown-body" v-html="renderMarkdown(quiz?.description)"></div>
      <div class="meta-row">
        <span v-if="quiz?.time_limit_min">⏱ {{ quiz.time_limit_min }} phút</span>
        <span v-if="quiz?.max_attempts">🔁 Tối đa {{ quiz.max_attempts }} lần</span>
        <span v-if="quiz?.deadline">📅 Hạn: {{ new Date(quiz.deadline).toLocaleString('vi-VN') }}</span>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button :disabled="loading" @click="startAttempt">Bắt đầu làm bài</button>
    </div>

    <!-- In-progress state -->
    <div v-else-if="!submitted">
      <div class="quiz-header">
        <h2>{{ quiz?.title }}</h2>
        <div v-if="timeLeft !== null" class="timer" :class="{ warning: timeLeft < 60 }">
          ⏱ {{ formatTime(timeLeft) }}
        </div>
      </div>

      <div v-for="(q, idx) in attempt.questions" :key="q.id" class="question">
        <div class="q-text">
          <strong>{{ idx + 1 }}.</strong> <span v-html="renderMarkdown(q.question_text)"></span>
        </div>
        <div v-for="choice in q.choices" :key="choice.id" class="choice" @click="toggleChoice(q, choice.id)">
          <input
            v-if="q.question_type === 'multi'"
            type="checkbox"
            :checked="answersMap[q.id]?.includes(choice.id)"
            readonly
          />
          <input
            v-else
            type="radio"
            :name="q.id"
            :checked="answersMap[q.id]?.[0] === choice.id"
            readonly
          />
          <span v-html="renderMarkdown(choice.text)"></span>
        </div>
      </div>

      <p v-if="submitError" class="error">{{ submitError }}</p>
      <button :disabled="submitting" @click="submitQuiz">
        {{ submitting ? 'Đang nộp…' : 'Nộp bài' }}
      </button>
    </div>

    <!-- Result state -->
    <div v-else class="results">
      <h2>Kết quả</h2>
      <div class="score-box" v-if="result?.score !== undefined">
        <span class="score">{{ result?.score }} / {{ result?.max_score }}</span>
        <span class="pct">{{ result ? Math.round((result.score / result.max_score) * 100) : 0 }}%</span>
      </div>
      <div v-else class="info-msg">
        Kết quả sẽ được hiển thị {{ quiz?.show_result_after === 'deadline' ? 'sau khi hết hạn' : 'theo cài đặt của giáo viên' }}.
      </div>
      <div v-if="result?.answers?.length" class="answer-review">
        <div v-for="(a, idx) in result.answers" :key="a.question_id" class="review-item" :class="a.is_correct ? 'correct' : 'wrong'">
          <strong>{{ idx + 1 }}.</strong> {{ a.is_correct ? '✓ Đúng' : '✗ Sai' }}
          <div v-if="a.explanation" class="explanation" v-html="renderMarkdown(a.explanation)"></div>
        </div>
      </div>
      <RouterLink :to="`/classes/${classId}`" class="btn">Quay lại lớp</RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'
import { useMarkdown } from '@/composables/useMarkdown'

const { renderMarkdown } = useMarkdown()

const route = useRoute()
const classId = route.params.classId as string
const quizId = route.params.quizId as string

const loading = ref(false)
const quiz = ref<any>(null)
const attempt = ref<any>(null)
const submitted = ref(false)
const submitting = ref(false)
const result = ref<any>(null)
const error = ref('')
const submitError = ref('')

// answers: { [questionId]: string[] }
const answersMap = ref<Record<string, string[]>>({})

// Timer
const timeLeft = ref<number | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

function formatTime(sec: number) {
  const m = Math.floor(sec / 60).toString().padStart(2, '0')
  const s = (sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function startTimer(limitMin: number) {
  timeLeft.value = limitMin * 60
  timer = setInterval(() => {
    if (timeLeft.value === null) return
    timeLeft.value -= 1
    if (timeLeft.value <= 0) {
      clearInterval(timer!)
      submitQuiz()
    }
  }, 1000)
}

onUnmounted(() => { if (timer) clearInterval(timer) })

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get(`/classes/${classId}/quizzes`)
    quiz.value = (data as any[]).find((q: any) => q.id === quizId) || null
  } finally { loading.value = false }
})

async function startAttempt() {
  error.value = ''; loading.value = true
  try {
    const { data } = await api.post(`/quizzes/${quizId}/attempts`)
    attempt.value = data
    data.questions.forEach((q: any) => { answersMap.value[q.id] = [] })
    if (data.time_limit_min) startTimer(data.time_limit_min)
  } catch (e: any) { error.value = e?.response?.data?.detail ?? 'Không thể bắt đầu quiz' }
  finally { loading.value = false }
}

function toggleChoice(q: any, choiceId: string) {
  if (!answersMap.value[q.id]) answersMap.value[q.id] = []
  if (q.question_type === 'multi') {
    const idx = answersMap.value[q.id].indexOf(choiceId)
    if (idx === -1) answersMap.value[q.id].push(choiceId)
    else answersMap.value[q.id].splice(idx, 1)
  } else {
    answersMap.value[q.id] = [choiceId]
  }
}

async function submitQuiz() {
  if (submitting.value) return
  if (timer) clearInterval(timer)
  submitting.value = true
  submitError.value = ''
  try {
    const answers = Object.entries(answersMap.value).map(([question_id, chosen_ids]) => ({
      question_id,
      chosen_ids,
    }))
    const { data } = await api.patch(`/quizzes/${quizId}/attempts/${attempt.value.attempt_id}/submit`, { answers })
    result.value = data
    submitted.value = true
  } catch (e: any) {
    submitError.value = e?.response?.data?.detail ?? 'Nộp thất bại'
  } finally { submitting.value = false }
}
</script>

<style scoped>
.back { color: #666; text-decoration: none; font-size: 0.9rem; }
h1, h2 { margin: 0.5rem 0 0.5rem; }
.meta-row { display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.9rem; color: #666; margin: 0.5rem 0 1rem; }
button { padding: 0.6rem 1.5rem; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; margin-top: 1rem; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.quiz-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.timer { font-size: 1.2rem; font-weight: 700; color: #333; }
.timer.warning { color: red; }
.question { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
.q-text { margin: 0 0 0.75rem; }
.choice { display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0; cursor: pointer; }
.choice:hover { color: #1a6ef5; }
.error { color: red; margin-top: 0.5rem; }
.results { max-width: 600px; }
.score-box { display: flex; align-items: baseline; gap: 1rem; margin: 1rem 0; }
.score { font-size: 2.5rem; font-weight: 700; color: #1a1a2e; }
.pct { font-size: 1.5rem; color: #666; }
.answer-review { margin-top: 1rem; }
.review-item { padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.5rem; }
.correct { background: #d4edda; }
.wrong { background: #f8d7da; }
.explanation { font-size: 0.85rem; color: #555; margin: 0.25rem 0 0; }
.btn { display: inline-block; margin-top: 1.5rem; padding: 0.6rem 1.5rem; background: #1a1a2e; color: #fff; border-radius: 4px; text-decoration: none; }
</style>
