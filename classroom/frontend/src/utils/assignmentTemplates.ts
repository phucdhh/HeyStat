/**
 * Lesson-ready blueprints for a jamovi assignment.
 *
 * Each blueprint only seeds what the auto-grader can already score on its own: the
 * analyses a student must have run (`op: 'ran'`), matched against the table titles
 * jamovi writes into the submitted .omv. Questions whose expected value a teacher
 * has not typed yet are put in the description instead, because an answer_key
 * question with no answer would grade every submission as wrong.
 *
 * Titles are the ones jmv/scatr render (jmv/jamovi/0000.yaml); the grader folds
 * case, spacing and accents, so "T-Test" still lands on "One Sample T-Test".
 */

export interface AssignmentBlueprint {
  id: string
  group: string
  label: string
  hint: string
  analyses: string[]
  /** extra { op, table } criteria beyond "the analysis was run" */
  extraChecks?: { op: string; table: string; label: string }[]
  asks: string[]
  points: number
}

export const BLANK_BLUEPRINT: AssignmentBlueprint = {
  id: 'blank',
  group: '',
  label: 'Tự cấu hình',
  hint: 'Bài tập trống, bạn tự thêm tiêu chí chấm sau khi tạo.',
  analyses: [],
  asks: [],
  points: 1,
}

export const ASSIGNMENT_BLUEPRINTS: AssignmentBlueprint[] = [
  {
    id: 'descriptives', group: 'Mô tả & khám phá dữ liệu', label: 'Thống kê mô tả',
    hint: 'Mẫu gồm bao nhiêu người, giá trị trung bình, SD, trung vị, tứ phân vị.',
    analyses: ['Descriptives'],
    asks: ['Cỡ mẫu (N) của biến là bao nhiêu?', 'Giá trị trung bình bằng bao nhiêu?', 'Độ lệch chuẩn bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'normality', group: 'Mô tả & khám phá dữ liệu', label: 'Kiểm định phân phối chuẩn',
    hint: 'Shapiro–Wilk / Kolmogorov–Smirnov cho từng biến định lượng.',
    analyses: ['Descriptives'],
    extraChecks: [{ op: 'present', table: 'Tests of Normality', label: 'Bảng "Tests of Normality" xuất hiện' }],
    asks: ['Giá trị p của kiểm định chuẩn tắc bằng bao nhiêu?', 'Biến có tuân luật chuẩn ở mức ý nghĩa 5% không?'],
    points: 1,
  },
  {
    id: 'missing', group: 'Mô tả & khám phá dữ liệu', label: 'Kiểm tra thiếu sót dữ liệu',
    hint: 'Đếm giá trị thiếu theo biến và theo nhóm.',
    analyses: ['Descriptives'],
    asks: ['Có bao nhiêu giá trị thiếu?', 'Thiếu nhiều nhất ở nhóm nào?'],
    points: 1,
  },
  {
    id: 'ttest_is', group: 'So sánh hai nhóm', label: 'T-test hai mẫu độc lập',
    hint: 'So sánh trung bình giữa hai nhóm, kèm kiểm định phương sai và cỡ hiệu ứng.',
    analyses: ['Independent Samples T-Test'],
    asks: ['Trung bình của nhóm 1 bằng bao nhiêu?', 'Trung bình của nhóm 2 bằng bao nhiêu?', 'Giá trị p của kiểm định bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'ttest_paired', group: 'So sánh hai nhóm', label: 'T-test cặp đôi (trước – sau)',
    hint: 'So sánh hai lần đo trên cùng một đối tượng.',
    analyses: ['Paired Samples T-Test'],
    asks: ['Mức chênh lệch trung bình trước – sau bằng bao nhiêu?', 'Giá trị p bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'ttest_one', group: 'So sánh hai nhóm', label: 'T-test một mẫu',
    hint: 'So sánh trung bình mẫu với một giá trị tham chiếu.',
    analyses: ['One Sample T-Test'],
    asks: ['Trung bình mẫu bằng bao nhiêu?', 'Khoảng tin cậy 95% là bao nhiêu?'],
    points: 1,
  },
  {
    id: 'anova_oneway', group: 'So sánh từ ba nhóm', label: 'ANOVA một chiều',
    hint: 'Một yếu tố nhiều mức, kèm kiểm định hậu nghiệm Tukey.',
    analyses: ['One-Way ANOVA'],
    asks: ['Giá trị F và bậc tự do bằng bao nhiêu?', 'p của kiểm định ANOVA bằng bao nhiêu?', 'Nhóm nào khác biệt có ý nghĩa ở hậu nghiệm Tukey?'],
    points: 1,
  },
  {
    id: 'anova_factorial', group: 'So sánh từ ba nhóm', label: 'ANOVA hai nhân tố',
    hint: 'Tác động chính và tác động tương tác của hai yếu tố.',
    analyses: ['ANOVA'],
    asks: ['F của tác động chính bằng bao nhiêu?', 'Có tác động tương tác có ý nghĩa thống kê không?'],
    points: 1,
  },
  {
    id: 'anova_rm', group: 'So sánh từ ba nhóm', label: 'ANOVA đo lặp',
    hint: 'Ba lần đo trở lên trên cùng một nhóm đối tượng.',
    analyses: ['Repeated Measures ANOVA'],
    asks: ['F của yếu tố thời gian bằng bao nhiêu?', 'Kiểm định phương sai đồng đều (Mauchly sphericity) có đạt không?'],
    points: 1,
  },
  {
    id: 'ancova', group: 'So sánh từ ba nhóm', label: 'ANCOVA (có hiệp biến)',
    hint: 'So sánh các nhóm sau khi hiệu chỉnh một hiệp biến.',
    analyses: ['ANCOVA'],
    asks: ['Trung bình hiệu chỉnh của mỗi nhóm là bao nhiêu?', 'p của yếu tố nhóm sau hiệu chỉnh bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'krs', group: 'So sánh từ ba nhóm', label: 'Kruskal–Wallis (phi tham số)',
    hint: 'Thay cho ANOVA một chiều khi vi phạm giả định.',
    analyses: ['One-Way ANOVA (Non-parametric)'],
    asks: ['Giá trị H bằng bao nhiêu?', 'p bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'correlation', group: 'Quan hệ & dự báo', label: 'Tương quan Pearson / Spearman',
    hint: 'Ma trận hệ số tương quan kèm giá trị p.',
    analyses: ['Correlation Matrix'],
    asks: ['Hệ số tương quan r giữa hai biến bằng bao nhiêu?', 'p bằng bao nhiêu?', 'Hướng và độ mạnh của quan hệ?'],
    points: 1,
  },
  {
    id: 'partial_corr', group: 'Quan hệ & dự báo', label: 'Tương quan bậc hai (partial)',
    hint: 'Quan hệ giữa hai biến khi kiểm soát biến thứ ba.',
    analyses: ['Partial Correlation'],
    asks: ['Hệ số tương quan bậc hai bằng bao nhiêu?', 'Khác gì so với tương quan thường?'],
    points: 1,
  },
  {
    id: 'linreg', group: 'Quan hệ & dự báo', label: 'Hồi quy tuyến tính bội',
    hint: 'Một biến phụ thuộc với nhiều biến độc lập, kèm giả định mô hình.',
    analyses: ['Linear Regression'],
    extraChecks: [{ op: 'present', table: 'Model Coefficients', label: 'Bảng "Model Coefficients" xuất hiện' }],
    asks: ['R² của mô hình bằng bao nhiêu?', 'Hệ số hồi quy chưa chuẩn hoá của biến X bằng bao nhiêu?', 'Biến nào có ý nghĩa thống kê (p < .05)?'],
    points: 1,
  },
  {
    id: 'logistic', group: 'Quan hệ & dự báo', label: 'Hồi quy logistic nhị phân',
    hint: 'Kết cục có/không, đọc OR và khoảng tin cậy.',
    analyses: ['Binomial Logistic Regression'],
    asks: ['Hệ số B của biến dự báo bằng bao nhiêu?', 'OR và khoảng tin cậy 95% bằng bao nhiêu?', 'p bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'contingency', group: 'Tỷ lệ & bảng chéo', label: 'Chi-square bảng 2×2',
    hint: 'So sánh tỷ lệ giữa các nhóm, kèm cỡ hiệu ứng.',
    analyses: ['Contingency Tables'],
    asks: ['Giá trị Chi-square và p bằng bao nhiêu?', 'Tỷ lệ ở mỗi nhóm là bao nhiêu?'],
    points: 1,
  },
  {
    id: 'prop_one', group: 'Tỷ lệ & bảng chéo', label: 'Kiểm định một tỷ lệ (binomial)',
    hint: 'So sánh tỷ lệ quan sát với một tỷ lệ kỳ vọng.',
    analyses: ['Proportion Test (2 Outcomes)'],
    asks: ['Tỷ lệ quan sát được bằng bao nhiêu?', 'p của kiểm định nhị thức bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'prop_n', group: 'Tỷ lệ & bảng chéo', label: 'So sánh nhiều tỷ lệ',
    hint: 'Nhiều hơn hai kết cục, kiểm định tỷ lệ như kỳ vọng.',
    analyses: ['Proportion Test (N Outcomes)'],
    asks: ['Tỷ lệ từng kết cục bằng bao nhiêu?', 'p của kiểm định bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'mcnemar', group: 'Tỷ lệ & bảng chéo', label: 'McNemar (trước – sau có cặp)',
    hint: 'Cùng một đối tượng đo hai lần trên một biến nhị phân.',
    analyses: ['Paired Samples Contingency Tables'],
    asks: ['Bảng chéo trước – sau gồm các ô nào?', 'p của kiểm định McNemar bằng bao nhiêu?'],
    points: 1,
  },
  {
    id: 'reliability', group: 'Đo lường & nhân tố', label: 'Độ tin cậy Cronbach’s α',
    hint: 'Thang đo nhiều mục, đọc α và α nếu bỏ mục.',
    analyses: ['Reliability Analysis'],
    asks: ['Cronbach’s α của thang đo bằng bao nhiêu?', 'Mục nào nên bỏ vì làm giảm α?'],
    points: 1,
  },
  {
    id: 'efa', group: 'Đo lường & nhân tố', label: 'Phân tích nhân tố khám phá (EFA)',
    hint: 'Xoay principal components / oblique, đọc phương sai tích luỹ.',
    analyses: ['Exploratory Factor Analysis'],
    asks: ['Có bao nhiêu nhân tố được rút ra?', 'Phương sai tích luỹ giải thích được bao nhiêu %?', 'Mục nào tải (loading) < .5?'],
    points: 1,
  },
  {
    id: 'pca', group: 'Đo lường & nhân tố', label: 'Phân tích thành phần chính (PCA)',
    hint: 'Giảm chiều dữ liệu, đọc eigenvalue và biểu đồ stone scree.',
    analyses: ['Principal Component Analysis'],
    asks: ['Thành phần thứ nhất giải thích bao nhiêu % phương sai?', 'Có mấy thành phần với eigenvalue > 1?'],
    points: 1,
  },
]

export const BLUEPRINT_GROUPS = [...new Set(ASSIGNMENT_BLUEPRINTS.map((b) => b.group))]

/** What the auto-grader will score straight after the assignment is created. */
export function checksOf(b: AssignmentBlueprint) {
  const rows = [
    ...b.analyses.map((analysis) => ({ op: 'ran', analysis, label: `Chạy “${analysis}”` })),
    ...(b.extraChecks ?? []).map((c) => ({ op: c.op, table: c.table, label: c.label })),
  ]
  return rows.map((c, i) => ({ id: `c${i + 1}`, points: b.points, explain: '', ...c }))
}

export function descriptionOf(b: AssignmentBlueprint) {
  if (b.id === 'blank') return ''
  const steps = [
    ...b.analyses.map((a) => `Chạy phân tích “${a}” trong phiên HeyStat của bài tập.`),
    'Nhấn “Đồng bộ kết quả”, tick các bảng kết quả làm bằng chứng.',
    'Trả lời câu hỏi ở thanh bên rồi nhấn “Nộp bài”. Bài được chấm tự động theo các bảng này.',
  ]
  return [
    b.hint,
    '',
    'Các bước làm bài:',
    ...steps.map((s, i) => `${i + 1}. ${s}`),
    '',
    'Câu hỏi phải trả lời:',
    ...b.asks.map((q, i) => `${i + 1}. ${q}`),
  ].join('\n')
}

/** The list only stores homework/project/exam, so that is what the chip can say. */
export const kindLabel = (a: any): string =>
  a?.assignment_type === 'exam' ? 'Kiểm tra'
    : a?.assignment_type === 'project' ? 'Thực hành'
    : 'Bài tập'
