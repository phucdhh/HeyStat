<template>
  <span v-if="entry" class="stat-help" tabindex="0">
    <span class="col">{{ text }}</span>
    <span class="mark">?</span>
    <span class="card" role="tooltip">
      <strong>{{ entry.label }}</strong>
      <p><em>Là gì:</em> {{ entry.what }}</p>
      <p><em>Cách đọc:</em> {{ entry.read }}</p>
      <p><em>Cẩn thận:</em> {{ entry.watch }}</p>
      <p class="apa"><em>Kiểu APA:</em> {{ entry.apa }}</p>
    </span>
  </span>
  <span v-else class="col">{{ text }}</span>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useHelp } from '@/composables/useHelp'

const props = defineProps<{ text: string }>()

const { entries, load, match } = useHelp()
const entry = computed(() => (entries.value.length ? match(props.text) : null))

onMounted(() => { if (!entries.value.length) load() })
</script>

<style scoped>
.stat-help { position: relative; display: inline-block; cursor: help; }
.col { border-bottom: 1px dotted #b9a06b; }
.mark {
  margin-left: 0.25rem; font-size: 0.62rem; font-weight: 700; line-height: 1;
  color: #78350f; background: #fde68a; border-radius: 50%; padding: 0.18rem 0.3rem;
}
.card {
  display: none; position: absolute; bottom: 130%; left: 0; z-index: 40;
  width: 20rem; max-width: 70vw; padding: 0.7rem 0.8rem;
  background: #fffdf5; color: #1a1a2e; border: 1px solid #e2c9a0; border-radius: 8px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15); font-size: 0.78rem; font-weight: 400;
  text-align: left; line-height: 1.45; white-space: normal; cursor: auto;
}
.stat-help:hover .card, .stat-help:focus .card { display: block; }
.card strong { display: block; margin-bottom: 0.3rem; font-size: 0.82rem; }
.card p { margin: 0.25rem 0; }
.card em { color: #92400e; font-style: normal; font-weight: 700; }
.apa { font-family: ui-monospace, monospace; }
</style>
