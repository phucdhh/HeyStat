<template>
  <div>
    <div v-if="loading">Đang tải…</div>
    <div v-else-if="lesson">
      <RouterLink :to="`/classes/${classId}`" class="back">← Quay lại lớp</RouterLink>
      <h1>{{ lesson.title }}</h1>
      <div class="content" v-html="sanitized" />

      <div v-if="resources.length" class="resources">
        <h3>Tài nguyên</h3>
        <div v-for="r in resources" :key="r.id" class="resource-item">
          <div v-if="r.resource_type === 'embed'" class="embed-wrapper">
            <iframe
              :src="r.url"
              allowfullscreen
              class="embed-frame"
              sandbox="allow-scripts allow-same-origin allow-presentation"
            />
          </div>
          <div v-else-if="r.resource_type === 'link'">
            <a :href="r.url" target="_blank" rel="noopener noreferrer">{{ r.title }}</a>
          </div>
          <div v-else-if="r.resource_type === 'file'">
            <a :href="r.url" target="_blank">📎 {{ r.title }}</a>
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

const route = useRoute()
const classId = route.params.classId as string
const lessonId = route.params.lessonId as string

const loading = ref(true)
const lesson = ref<any>(null)
const resources = ref<any[]>([])

const { renderMarkdown } = useMarkdown()
const sanitized = computed(() => lesson.value ? renderMarkdown(lesson.value.content || '') : '')

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
h1 { margin: 0.5rem 0 1rem; }
.content { line-height: 1.7; color: #333; }
.resources { margin-top: 2rem; }
.resources h3 { margin-bottom: 0.75rem; }
.resource-item { margin-bottom: 1rem; }
.embed-wrapper { position: relative; padding-bottom: 56.25%; height: 0; }
.embed-frame { position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; border-radius: 4px; }
a { color: #1a6ef5; }
</style>
