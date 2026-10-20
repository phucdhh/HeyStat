<template>
  <figure class="apa-table">
    <figcaption>
      <span v-if="table.analysis" class="analysis">{{ table.analysis }}</span>
      <span class="title">{{ table.title || 'Bảng kết quả' }}</span>
    </figcaption>
    <table>
      <thead>
        <tr>
          <th v-for="(c, i) in table.columns" :key="i"><StatHelp :text="c" /></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, r) in table.rows" :key="r">
          <td v-for="(cell, i) in row" :key="i">{{ cell }}</td>
        </tr>
      </tbody>
    </table>
  </figure>
</template>

<script setup lang="ts">
import StatHelp from '@/components/StatHelp.vue'

defineProps<{ table: { analysis?: string; title?: string; columns: string[]; rows: string[][] } }>()
</script>

<style scoped>
.apa-table { border: 1px solid #eee; border-radius: 6px; padding: 0.6rem 0.7rem; background: #fff; margin-bottom: 1rem; }
figcaption { margin-bottom: 0.4rem; font-size: 0.78rem; }
.analysis { display: block; color: #92400e; font-weight: 700; }
.title { color: #444; }
table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
th, td { padding: 0.25rem 0.45rem; text-align: left; border-bottom: 1px solid #f2f2f2; white-space: nowrap; }
th { font-weight: 700; background: #fafafa; }
</style>
