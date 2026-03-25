<template>
  <div class="quiz-builder">
    <RouterLink :to="`/classes/${classId}`" class="back">← Quay lại lớp</RouterLink>
    <h1>Tạo Quiz Mới</h1>
    <p v-if="error" class="error">{{ error }}</p>

    <!-- Quiz Settings -->
    <div class="card settings-card">
      <h3>Cài đặt chung</h3>
      <div class="form-group">
        <label>Tiêu đề</label>
        <input v-model="form.title" type="text" placeholder="Nhập tiêu đề quiz..." required />
      </div>
      <div class="form-group row">
        <div>
          <label>Mô tả (Hỗ trợ Markdown & KaTeX)</label>
          <textarea v-model="form.description" rows="3" placeholder="Ví dụ: Kiểm tra kiến thức $H_0$"></textarea>
        </div>
        <div class="preview-box">
          <label>Xem trước mô tả:</label>
          <div class="markdown-body" v-html="renderMarkdown(form.description)"></div>
        </div>
      </div>
      <div class="form-group row">
        <div>
          <label>Thời gian (phút)</label>
          <input v-model.number="form.time_limit_min" type="number" min="0" placeholder="0 = Không giới hạn" />
        </div>
        <div>
          <label>Số lần làm tối đa</label>
          <input v-model.number="form.max_attempts" type="number" min="0" placeholder="0 = Không giới hạn" />
        </div>
        <div>
          <label>Hiển thị kết quả</label>
          <select v-model="form.show_result_after">
            <option value="submit">Ngay sau khi nộp</option>
            <option value="deadline">Sau khi hết hạn</option>
            <option value="never">Không hiển thị</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>Hạn chót</label>
        <input v-model="form.deadline" type="datetime-local" />
      </div>
    </div>

    <!-- Questions list -->
    <div class="card">
      <h3>Câu hỏi ({{ questions.length }})</h3>
      
      <div v-for="(q, qIndex) in questions" :key="qIndex" class="question-editor">
        <div class="q-header">
          <strong>Câu {{ qIndex + 1 }}</strong>
          <div>
            <span class="type-select">
              <select v-model="q.question_type">
                <option value="single">Một đáp án (Radio)</option>
                <option value="multi">Nhiều đáp án (Checkbox)</option>
              </select>
            </span>
            <button class="small-btn danger" @click="removeQuestion(qIndex)">Xoá câu này</button>
          </div>
        </div>

        <div class="form-group row">
          <div>
            <textarea v-model="q.question_text" rows="3" placeholder="Nội dung câu hỏi (Markdown/KaTeX)"></textarea>
          </div>
          <div class="preview-box">
            <div class="markdown-body" v-html="renderMarkdown(q.question_text)"></div>
          </div>
        </div>

        <div class="choices">
          <div v-for="(choice, cIndex) in q.choices" :key="cIndex" class="choice-editor">
            <input 
              :type="q.question_type === 'single' ? 'radio' : 'checkbox'" 
              :checked="choice.is_correct"
              @change="toggleCorrect(q, cIndex)"
            />
            <input v-model="choice.text" type="text" placeholder="Đáp án..." class="choice-input" />
            <button class="icon-btn" @click="removeChoice(q, cIndex)">❌</button>
          </div>
          <button class="small-btn" @click="addChoice(q)">+ Thêm đáp án</button>
        </div>

        <div class="form-group mt-2">
          <label>Giải thích sau khi nộp (tùy chọn)</label>
          <input v-model="q.explanation" type="text" placeholder="Giải thích đáp án (Markdown/KaTeX)" />
          <div v-if="q.explanation" class="markdown-body px-2" v-html="renderMarkdown(q.explanation)"></div>
        </div>
      </div>

      <button class="add-q-btn" @click="addQuestion">+ Thêm câu hỏi mới</button>
    </div>

    <div class="actions">
      <button :disabled="submitting" @click="saveQuiz" class="save-btn">
        {{ submitting ? 'Đang lưu...' : 'Lưu Quiz' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import { useMarkdown } from '@/composables/useMarkdown'

const route = useRoute()
const router = useRouter()
const classId = route.params.classId as string

const { renderMarkdown } = useMarkdown()

const form = ref({
  title: '',
  description: '',
  time_limit_min: null as number | null,
  max_attempts: 1,
  show_result_after: 'submit',
  deadline: ''
})

interface Choice {
  text: string
  is_correct: boolean
}

interface Question {
  question_type: 'single' | 'multi'
  question_text: string
  points: number
  explanation: string
  choices: Choice[]
}

const questions = ref<Question[]>([
  {
    question_type: 'single',
    question_text: '',
    points: 1,
    explanation: '',
    choices: [
      { text: '', is_correct: true },
      { text: '', is_correct: false }
    ]
  }
])

const error = ref('')
const submitting = ref(false)

function addQuestion() {
  questions.value.push({
    question_type: 'single',
    question_text: '',
    points: 1,
    explanation: '',
    choices: [
      { text: '', is_correct: true },
      { text: '', is_correct: false }
    ]
  })
}

function removeQuestion(idx: number) {
  questions.value.splice(idx, 1)
}

function addChoice(q: Question) {
  q.choices.push({ text: '', is_correct: false })
}

function removeChoice(q: Question, cIndex: number) {
  q.choices.splice(cIndex, 1)
}

function toggleCorrect(q: Question, targetIdx: number) {
  if (q.question_type === 'single') {
    q.choices.forEach((c, idx) => {
      c.is_correct = (idx === targetIdx)
    })
  } else {
    q.choices[targetIdx].is_correct = !q.choices[targetIdx].is_correct
  }
}

async function saveQuiz() {
  if (!form.value.title.trim()) {
    error.value = 'Vui lòng nhập tiêu đề'
    return
  }
  for (const [i, q] of Object.entries(questions.value)) {
    if (!q.question_text.trim()) {
      error.value = `Câu hỏi ${Number(i) + 1} không được để trống`
      return
    }
    if (q.choices.length < 2) {
      error.value = `Câu hỏi ${Number(i) + 1} cần có ít nhất 2 đáp án`
      return
    }
    if (!q.choices.some(c => c.is_correct)) {
      error.value = `Câu hỏi ${Number(i) + 1} chưa chọn đáp án đúng`
      return
    }
  }

  error.value = ''
  submitting.value = true

  try {
    const payload = {
      ...form.value,
      class_id: classId,
      time_limit_min: form.value.time_limit_min || null,
      max_attempts: form.value.max_attempts || null,
      deadline: form.value.deadline ? new Date(form.value.deadline).toISOString() : null,
      questions: questions.value
    }
    await api.post(`/classes/${classId}/quizzes`, payload)
    router.push(`/classes/${classId}`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Lỗi khi lưu quiz'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.quiz-builder {
  max-width: 900px;
  margin: 0 auto;
}
.back {
  display: inline-block;
  margin-bottom: 1rem;
  color: #666;
  text-decoration: none;
}
.card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 2rem;
}
.settings-card { background: #fdfdfd; }
.form-group {
  margin-bottom: 1rem;
}
.form-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}
.form-group input[type="text"],
.form-group input[type="number"],
.form-group input[type="datetime-local"],
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.preview-box {
  background: #f9f9f9;
  border: 1px dashed #ddd;
  border-radius: 4px;
  padding: 0.5rem;
  min-height: 3rem;
  overflow-y: auto;
}
.question-editor {
  border: 1px solid #eee;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
  background: #fcfcfc;
}
.q-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1rem;
  align-items: center;
}
.type-select {
  margin-right: 1rem;
}
.choices {
  margin-top: 1rem;
  padding-left: 1rem;
}
.choice-editor {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.choice-input {
  flex: 1;
  padding: 0.4rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}
.small-btn {
  padding: 0.3rem 0.6rem;
  background: #e9ecef;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}
.danger { color: white; background: #dc3545; }
.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.5;
}
.icon-btn:hover { opacity: 1; }
.add-q-btn {
  width: 100%;
  padding: 0.8rem;
  background: #f0f4f8;
  border: 2px dashed #bbb;
  border-radius: 6px;
  font-weight: bold;
  color: #333;
  cursor: pointer;
}
.actions {
  text-align: right;
  margin-bottom: 2rem;
}
.save-btn {
  padding: 0.8rem 2rem;
  background: #1a1a2e;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1.1rem;
  font-weight: bold;
  cursor: pointer;
}
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #dc3545; font-weight: bold; }
</style>