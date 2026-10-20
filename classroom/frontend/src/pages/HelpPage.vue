<template>
  <div class="help">
    <h1>Cách đọc bảng kết quả HeyStat</h1>
    <p class="lead">
      Mỗi cột trong bảng kết quả jamovi có một bóng hỏi <span class="mark">?</span> ngay trong bài làm:
      rê chuột vào đó để xem chỉ số này là gì, đọc ra sao và trình bày theo kiểu APA thế nào.
    </p>

    <div v-if="loading" class="loading">Đang tải hướng dẫn…</div>
    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else class="grid">
      <article v-for="e in entries" :key="e.key" :id="e.key">
        <h2>{{ e.label }}</h2>
        <p class="aliases">{{ e.aliases.join(' · ') }}</p>
        <dl>
          <dt>Là gì</dt><dd>{{ e.what }}</dd>
          <dt>Cách đọc</dt><dd>{{ e.read }}</dd>
          <dt>Cẩn thận</dt><dd>{{ e.watch }}</dd>
          <dt>Kiểu APA</dt><dd class="apa">{{ e.apa }}</dd>
        </dl>
      </article>
    </div>

    <h2 class="steps-title">Quy trình nộp bài</h2>
    <ol class="steps">
      <li>Vào bài tập, chọn <strong>Làm bài</strong> – HeyStat mở một bản sao dữ liệu riêng cho bạn.</li>
      <li>Chạy các phân tích trong HeyStat như bình thường.</li>
      <li>Nhấn <strong>🔄 Đồng bộ kết quả</strong> để đưa các bảng/biểu đồ đang có vào danh sách bằng chứng.</li>
      <li>Tích chọn những bảng giáo viên cần thấy, điền Phần 1 nếu bài tập có câu hỏi.</li>
      <li>Nhấn <strong>Nộp bài</strong>: phiên làm việc bị đóng băng, bài của bạn gồm cả file .omv lẫn các bảng đã chọn.</li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useHelp } from '@/composables/useHelp'

const { entries, error, loading, load } = useHelp()
onMounted(load)
</script>

<style scoped>
.help { max-width: 60rem; }
h1 { margin-bottom: 0.4rem; }
.lead { color: #555; font-size: 0.92rem; }
.mark {
  font-size: 0.62rem; font-weight: 700; color: #78350f; background: #fde68a;
  border-radius: 50%; padding: 0.18rem 0.3rem;
}
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); gap: 0.8rem; margin-top: 1rem; }
article { border: 1px solid #eee; border-radius: 8px; padding: 0.8rem 0.9rem; background: #fff; }
article h2 { margin: 0 0 0.2rem; font-size: 0.98rem; }
.aliases { margin: 0 0 0.5rem; font-size: 0.72rem; color: #92400e; font-family: ui-monospace, monospace; }
dl { margin: 0; font-size: 0.8rem; line-height: 1.5; }
dt { font-weight: 700; color: #6b7280; margin-top: 0.35rem; }
dd { margin: 0; }
.apa { font-family: ui-monospace, monospace; }
.steps-title { margin-top: 2rem; }
.steps { font-size: 0.88rem; line-height: 1.6; padding-left: 1.3rem; }
.loading { color: #888; }
.error { color: #b91c1c; }
</style>
