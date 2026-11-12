import{a as u}from"./client-CMVNaTTJ.js";const e=[{value:"standard",label:"Lý thuyết",icon:"📘",hint:"Giảng giải bằng Markdown, chèn được công thức",leadsWith:"nội dung bài giảng"},{value:"practical",label:"Thực hành HeyStat",icon:"📊",hint:"Đính kèm bộ dữ liệu .omv để học viên mở ra làm luôn",leadsWith:"nút mở bộ dữ liệu trong HeyStat"},{value:"video",label:"Video bài giảng",icon:"🎬",hint:"Nhúng video từ YouTube, Loom hoặc Vimeo",leadsWith:"video nhúng"},{value:"reading",label:"Tài liệu đọc",icon:"📄",hint:"PDF hoặc liên kết tài liệu, kèm ghi chú hướng dẫn đọc",leadsWith:"tài liệu đính kèm"}],d=n=>e.find(a=>a.value===n)??e[0],s=[{value:"video",label:"Video nhúng",icon:"🎬"},{value:"pdf",label:"PDF / tài liệu",icon:"📄"},{value:"link",label:"Liên kết",icon:"🔗"},{value:"data_file",label:"Bộ dữ liệu HeyStat",icon:"📊"}],g="Video/tài liệu nhúng chỉ nhận liên kết từ YouTube, Loom, Vimeo, Google Drive hoặc OneDrive.",o=n=>`# ${n}

`,m={standard:n=>o(n)+`## Mục tiêu

- Học xong bài này, bạn có thể…

## Nội dung chính

### 1. …

Viết giải thích ở đây. Công thức: $\\bar{x} = \\frac{1}{n}\\sum x_i$

## Ví dụ minh hoạ

- Chạy phân tích trong HeyStat rồi mô tả kết quả

## Tự kiểm tra

- Câu hỏi 1…
`,practical:n=>o(n)+`## Nhiệm vụ

- Mở bộ dữ liệu ở đầu trang này bằng HeyStat
- …

## Các bước

1. **Descriptives** → chọn biến …
2. **T-test** → kiểm định …

## Kết quả cần báo cáo

- Giá trị trung bình, độ lệch chuẩn, *p*, cỡ hiệu ứng

## Gợi ý diễn giải

Nêu kết luận thống kê rồi kết luận thực tế.
`,video:n=>o(n)+`## Trước khi xem

- Câu hỏi để học viên mang vào video: …

## Trong khi xem

- Ghi lại mốc thời gian của mỗi thao tác trong HeyStat

## Sau khi xem

- Làm lại thao tác với bộ dữ liệu của bạn
`,reading:n=>o(n)+`## Đọc ở đâu

- Tài liệu đính kèm ở đầu trang này

## Trọng tâm

- …

## Ghi chú sau khi đọc

- Điều bạn chưa hiểu: …
`},b=n=>`## ${n}

`;async function v(n,a,c){const i=window.open("about:blank","_blank");if(!i)throw new Error("Trình duyệt đã chặn tab mới. Hãy cho phép cửa sổ bật lên cho HeyStat rồi thử lại.");try{i.opener=null,i.document.title="Đang mở HeyStat…",i.document.body.textContent="Đang mở bộ dữ liệu trong HeyStat…"}catch{}try{const t=await u.post(`/classes/${n}/files/${a}/open-url`),l=t.data.filename??c,h=encodeURIComponent(`${window.location.origin}/api/v1/files/ot/${t.data.token}`);i.closed||i.location.replace(`${window.location.origin}/#open?url=${h}&title=${encodeURIComponent(l)}`)}catch(t){throw i.close(),t}}export{b as B,g as E,e as L,m as O,s as R,d as l,v as o};
