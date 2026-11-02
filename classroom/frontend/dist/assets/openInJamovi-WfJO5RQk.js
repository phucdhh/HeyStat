import{a as h}from"./client-BR8Nh0q-.js";const a=[{value:"standard",label:"Lý thuyết",icon:"📘",hint:"Giảng giải bằng Markdown, chèn được công thức",leadsWith:"nội dung bài giảng"},{value:"practical",label:"Thực hành HeyStat",icon:"📊",hint:"Đính kèm bộ dữ liệu .omv để học viên mở ra làm luôn",leadsWith:"nút mở bộ dữ liệu trong HeyStat"},{value:"video",label:"Video bài giảng",icon:"🎬",hint:"Nhúng video từ YouTube, Loom hoặc Vimeo",leadsWith:"video nhúng"},{value:"reading",label:"Tài liệu đọc",icon:"📄",hint:"PDF hoặc liên kết tài liệu, kèm ghi chú hướng dẫn đọc",leadsWith:"tài liệu đính kèm"}],s=n=>a.find(t=>t.value===n)??a[0],d=[{value:"video",label:"Video nhúng",icon:"🎬"},{value:"pdf",label:"PDF / tài liệu",icon:"📄"},{value:"link",label:"Liên kết",icon:"🔗"},{value:"data_file",label:"Bộ dữ liệu HeyStat",icon:"📊"}],g="Video/tài liệu nhúng chỉ nhận liên kết từ YouTube, Loom, Vimeo, Google Drive hoặc OneDrive.",i=n=>`# ${n}

`,r={standard:n=>i(n)+`## Mục tiêu

- Học xong bài này, bạn có thể…

## Nội dung chính

### 1. …

Viết giải thích ở đây. Công thức: $\\bar{x} = \\frac{1}{n}\\sum x_i$

## Ví dụ minh hoạ

- Chạy phân tích trong HeyStat rồi mô tả kết quả

## Tự kiểm tra

- Câu hỏi 1…
`,practical:n=>i(n)+`## Nhiệm vụ

- Mở bộ dữ liệu ở đầu trang này bằng HeyStat
- …

## Các bước

1. **Descriptives** → chọn biến …
2. **T-test** → kiểm định …

## Kết quả cần báo cáo

- Giá trị trung bình, độ lệch chuẩn, *p*, cỡ hiệu ứng

## Gợi ý diễn giải

Nêu kết luận thống kê rồi kết luận thực tế.
`,video:n=>i(n)+`## Trước khi xem

- Câu hỏi để học viên mang vào video: …

## Trong khi xem

- Ghi lại mốc thời gian của mỗi thao tác trong HeyStat

## Sau khi xem

- Làm lại thao tác với bộ dữ liệu của bạn
`,reading:n=>i(n)+`## Đọc ở đâu

- Tài liệu đính kèm ở đầu trang này

## Trọng tâm

- …

## Ghi chú sau khi đọc

- Điều bạn chưa hiểu: …
`},m=n=>`## ${n}

`;async function b(n,t,e){const o=await h.post(`/classes/${n}/files/${t}/open-url`),c=o.data.filename??e,l=encodeURIComponent(`${window.location.origin}/api/v1/files/ot/${o.data.token}`);window.open(`${window.location.origin}/#open?url=${l}&title=${encodeURIComponent(c)}`,"_blank")}export{m as B,g as E,a as L,r as O,d as R,s as l,b as o};
