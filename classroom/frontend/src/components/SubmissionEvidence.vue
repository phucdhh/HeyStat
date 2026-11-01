<template>
  <div class="evidence">
    <div v-if="answers.length" class="answers">
      <h4>Phần 1 – Trả lời của học viên</h4>
      <table>
        <tbody>
          <tr v-for="a in answers" :key="a.id">
            <td class="lbl">{{ a.label }}</td>
            <td>
              <div>{{ a.given ?? '—' }}</div>
              <p v-if="a.note" class="note">{{ a.note }}</p>
            </td>
            <td :class="a.passed === null ? 'muted' : a.passed ? 'ok' : 'bad'">
              {{ a.passed === null ? 'chưa chấm' : a.passed ? `đạt ${a.awarded}/${a.points}` : `0/${a.points}` }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="items.length" class="items">
      <h4>Kết quả chấm tiêu chí</h4>
      <ul>
        <li v-for="it in items" :key="it.id" :class="it.passed ? 'ok' : it.pending ? 'muted' : 'bad'">
          <strong>{{ it.passed ? '✓' : it.pending ? '·' : '✗' }} {{ it.label }}</strong>
          <span>
            {{ it.explanation }}
            <em v-if="it.actual !== null && it.actual !== undefined">· bài làm: {{ fmt(it.actual) }}</em>
          </span>
        </li>
      </ul>
    </div>

    <div v-if="tables.length">
      <h4>Phần 2 – Bảng / biểu đồ học viên nộp</h4>
      <OutputTable v-for="t in tables" :key="t.index" :table="t" />
    </div>
    <p v-else class="muted">Học viên không nộp bảng kết quả nào.</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import OutputTable from '@/components/OutputTable.vue'

const props = defineProps<{ submission: any }>()

const NOTE_SUFFIX = '_note'

const tables = computed(() => props.submission?.outputs ?? [])
const items = computed(() => props.submission?.auto_grade?.items ?? [])

const answers = computed(() => {
  const given: Record<string, any> = props.submission?.answers ?? {}
  const graded: Record<string, any> = {}
  for (const it of items.value) if (it.kind === 'answer') graded[it.id] = it
  // Free-text explanations ride along as "<qid>_note" and are never graded as a value.
  return Object.keys(given)
    .filter((id) => !id.endsWith(NOTE_SUFFIX))
    .map((id) => ({
      id,
      label: graded[id]?.label ?? id,
      given: given[id],
      note: given[id + NOTE_SUFFIX],
      passed: graded[id] ? (graded[id].pending ? null : !!graded[id].passed) : null,
      awarded: graded[id]?.awarded,
      points: graded[id]?.points,
    }))
})

function fmt(v: any) {
  return typeof v === 'object' ? JSON.stringify(v) : String(v)
}
</script>

<style scoped>
.evidence { font-size: 0.85rem; }
h4 { margin: 1rem 0 0.4rem; color: var(--amber-800); font-size: 0.9rem; }
table { width: 100%; border-collapse: collapse; }
td { padding: 0.28rem 0.4rem; border-bottom: 1px solid var(--amber-100); }
.lbl { font-weight: 600; width: 45%; }
.note { margin: 0.3rem 0 0; padding: 0.4rem 0.55rem; background: #faf7ef; border-left: 3px solid var(--amber-300); border-radius: 0 4px 4px 0; white-space: pre-wrap; color: #444; }
ul { list-style: none; margin: 0; padding: 0; }
li { padding: 0.3rem 0; border-bottom: 1px solid #f0f0f0; }
li strong { display: block; }
li span { color: #555; }
li em { color: #888; font-style: normal; }
.ok { color: #059669; }
.bad { color: #B91C1C; }
.muted { color: var(--color-text-muted); }
</style>
