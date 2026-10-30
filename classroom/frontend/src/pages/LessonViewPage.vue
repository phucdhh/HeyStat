<template>
  <div>
    <div v-if="loading">Đang tải…</div>
    <div v-else-if="lesson">
      <RouterLink :to="`/classes/${classId}`" class="back">← Quay lại lớp</RouterLink>
      <div class="head">
        <span class="type-badge">{{ type.icon }} {{ type.label }}</span>
        <h1>{{ lesson.title }}</h1>
      </div>

      <!-- A practical lesson exists to be worked on, so the dataset comes first. -->
      <div v-if="datasets.length" class="dataset-bar">
        <div v-for="r in datasets" :key="r.id" class="dataset-row">
          <button class="btn-primary" :disabled="opening[r.file_id]" @click="openDataset(r)">
            {{ opening[r.file_id] ? 'Đang mở HeyStat…' : `📊 Mở “${label(r)}” trong HeyStat` }}
          </button>
          <button class="btn-plain" @click="download(r.file_id, label(r))">Tải file .omv</button>
        </div>
      </div>

      <div v-if="lead" class="lead">
        <iframe v-if="lead.embed_url || lead.url" :src="lead.embed_url || lead.url" allowfullscreen
                class="lead-frame" sandbox="allow-scripts allow-same-origin allow-presentation" />
        <a v-else :href="lead.url" target="_blank" rel="noopener noreferrer">📄 {{ label(lead) }}</a>
      </div>

      <div class="content" v-html="sanitized" />

      <div v-if="others.length" class="resources">
        <h3>Tài nguyên</h3>
        <div v-for="r in others" :key="r.id" class="resource-item">
          <div v-if="r.resource_type === 'video' || r.resource_type === 'pdf'" class="embed-wrapper">
            <iframe
              :src="r.embed_url || r.url"
              allowfullscreen
              class="embed-frame"
              sandbox="allow-scripts allow-same-origin allow-presentation"
            />
          </div>
          <div v-else-if="r.resource_type === 'link'">
            <a :href="r.url" target="_blank" rel="noopener noreferrer">🔗 {{ r.title || r.url }}</a>
          </div>
          <div v-else-if="r.file_id">
            <a href="#" @click.prevent="download(r.file_id, r.title)">📎 {{ r.title || 'Tệp bài học' }}</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'
import { useMarkdown } from '@/composables/useMarkdown'
import { lessonTypeOf } from '@/utils/lessonTemplates'
import { openClassFileInJamovi } from '@/utils/openInJamovi'

const route = useRoute()
const classId = route.params.classId as string
const lessonId = route.params.lessonId as string

const loading = ref(true)
const lesson = ref<any>(null)
const resources = ref<any[]>([])
const opening = ref<Record<string, boolean>>({})

const { renderMarkdown } = useMarkdown()
const sanitized = computed(() => lesson.value ? renderMarkdown(lesson.value.content || '') : '')
const type = computed(() => lessonTypeOf(lesson.value?.lesson_type))

const datasets = computed(() => resources.value.filter(r => r.resource_type === 'data_file' && r.file_id))

// What the page opens with follows the format the teacher chose; the rest stays in the list.
const lead = computed(() => {
  const t = lesson.value?.lesson_type
  if (t === 'video') return resources.value.find(r => r.resource_type === 'video') ?? null
  if (t === 'reading') return resources.value.find(r => r.resource_type === 'pdf')
    ?? resources.value.find(r => r.resource_type === 'link') ?? null
  return null
})

const others = computed(() =>
  resources.value.filter(r => r !== lead.value && !datasets.value.includes(r)))

const label = (r: any) => r.title || 'bộ dữ liệu của bài học'

async function openDataset(r: any) {
  opening.value = { ...opening.value, [r.file_id]: true }
  try {
    await openClassFileInJamovi(classId, r.file_id, label(r))
  } catch {
    alert('Không mở được bộ dữ liệu trong HeyStat')
  } finally {
    opening.value = { ...opening.value, [r.file_id]: false }
  }
}

async function download(fileId: string, name?: string) {
  const res = await api.get(`/classes/${classId}/files/${fileId}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = name || 'lesson-file'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get(`/classes/${classId}/lessons/${lessonId}`)
    lesson.value = data
    resources.value = data.resources || []
  } finally { loading.value = false }
})
</script>

<style scoped>
.back { color: #666; text-decoration: none; font-size: 0.9rem; }
.head { margin-top: 0.5rem; }
.type-badge { display: inline-block; font-size: 0.75rem; font-weight: 700; color: var(--amber-700); background: var(--amber-100); border: 1px solid var(--amber-200); padding: 0.12rem 0.5rem; border-radius: 8px; }
h1 { margin: 0.4rem 0 1rem; }
.dataset-bar { margin: 0 0 1.25rem; padding: 0.85rem 1rem; border: 1.5px solid var(--amber-200); border-radius: 10px; background: var(--amber-50); }
.dataset-row { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 0.5rem 1.1rem; border-radius: 7px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: progress; }
.btn-plain { background: transparent; border: none; color: var(--amber-700); font-size: 0.85rem; cursor: pointer; text-decoration: underline; }
.lead { margin-bottom: 1.25rem; }
.lead-frame { width: 100%; aspect-ratio: 16 / 9; border: none; border-radius: 8px; }
.content { line-height: 1.7; color: #333; }
.resources { margin-top: 2rem; }
.resources h3 { margin-bottom: 0.75rem; }
.resource-item { margin-bottom: 1rem; }
.embed-wrapper { position: relative; padding-bottom: 56.25%; height: 0; }
.embed-frame { position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; border-radius: 4px; }
a { color: #1a6ef5; }
</style>
