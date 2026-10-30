/**
 * Lesson formats offered to the teacher, and the starting outline for each one.
 * The backend recognises the same four `lesson_type` values (see
 * `api/routers/lessons.py::LESSON_TYPES`), so keep the two lists in step.
 */
export interface LessonType {
  value: string
  label: string
  icon: string
  hint: string
  /** what the student page leads with once the lesson is opened */
  leadsWith: string
}

export const LESSON_TYPES: LessonType[] = [
  {
    value: 'standard', label: 'Lý thuyết', icon: '📘',
    hint: 'Giảng giải bằng Markdown, chèn được công thức',
    leadsWith: 'nội dung bài giảng',
  },
  {
    value: 'practical', label: 'Thực hành HeyStat', icon: '📊',
    hint: 'Đính kèm bộ dữ liệu .omv để học viên mở ra làm luôn',
    leadsWith: 'nút mở bộ dữ liệu trong HeyStat',
  },
  {
    value: 'video', label: 'Video bài giảng', icon: '🎬',
    hint: 'Nhúng video từ YouTube, Loom hoặc Vimeo',
    leadsWith: 'video nhúng',
  },
  {
    value: 'reading', label: 'Tài liệu đọc', icon: '📄',
    hint: 'PDF hoặc liên kết tài liệu, kèm ghi chú hướng dẫn đọc',
    leadsWith: 'tài liệu đính kèm',
  },
]

export const lessonTypeOf = (value?: string | null): LessonType =>
  LESSON_TYPES.find(t => t.value === value) ?? LESSON_TYPES[0]

/** Mirrors ResourceCreate in the API; `data_file` is the .omv route. */
export const RESOURCE_TYPES = [
  { value: 'video', label: 'Video nhúng', icon: '🎬' },
  { value: 'pdf', label: 'PDF / tài liệu', icon: '📄' },
  { value: 'link', label: 'Liên kết', icon: '🔗' },
  { value: 'data_file', label: 'Bộ dữ liệu HeyStat', icon: '📊' },
]

export const EMBED_HINT =
  'Video/tài liệu nhúng chỉ nhận liên kết từ YouTube, Loom, Vimeo, Google Drive hoặc OneDrive.'

const OUTLINE_HEADER = (title: string) => `# ${title}\n\n`

/**
 * Skeletons are deliberately short: a teacher who wants a blank page picks "Tự viết",
 * and an outline that is too long reads like homework rather than a draft.
 */
export const OUTLINES: Record<string, (title: string) => string> = {
  standard: (title: string) =>
    OUTLINE_HEADER(title) +
    '## Mục tiêu\n\n- Học xong bài này, bạn có thể…\n\n' +
    '## Nội dung chính\n\n### 1. …\n\nViết giải thích ở đây. Công thức: $\\bar{x} = \\frac{1}{n}\\sum x_i$\n\n' +
    '## Ví dụ minh hoạ\n\n- Chạy phân tích trong HeyStat rồi mô tả kết quả\n\n' +
    '## Tự kiểm tra\n\n- Câu hỏi 1…\n',
  practical: (title: string) =>
    OUTLINE_HEADER(title) +
    '## Nhiệm vụ\n\n- Mở bộ dữ liệu ở đầu trang này bằng HeyStat\n- …\n\n' +
    '## Các bước\n\n1. **Descriptives** → chọn biến …\n2. **T-test** → kiểm định …\n\n' +
    '## Kết quả cần báo cáo\n\n- Giá trị trung bình, độ lệch chuẩn, *p*, cỡ hiệu ứng\n\n' +
    '## Gợi ý diễn giải\n\nNêu kết luận thống kê rồi kết luận thực tế.\n',
  video: (title: string) =>
    OUTLINE_HEADER(title) +
    '## Trước khi xem\n\n- Câu hỏi để học viên mang vào video: …\n\n' +
    '## Trong khi xem\n\n- Ghi lại mốc thời gian của mỗi thao tác trong HeyStat\n\n' +
    '## Sau khi xem\n\n- Làm lại thao tác với bộ dữ liệu của bạn\n',
  reading: (title: string) =>
    OUTLINE_HEADER(title) +
    '## Đọc ở đâu\n\n- Tài liệu đính kèm ở đầu trang này\n\n' +
    '## Trọng tâm\n\n- …\n\n' +
    '## Ghi chú sau khi đọc\n\n- Điều bạn chưa hiểu: …\n',
}

export const BLANK_OUTLINE = (title: string) => `## ${title}\n\n`
