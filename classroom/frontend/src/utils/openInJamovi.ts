import api from '@/api/client'

export async function openClassFileInJamovi(classId: string, fileId: string, fallbackName: string) {
  // Safari only permits a new tab during the click, before any network await.
  const tab = window.open('about:blank', '_blank')
  if (!tab) throw new Error('Trình duyệt đã chặn tab mới. Hãy cho phép cửa sổ bật lên cho HeyStat rồi thử lại.')
  try {
    tab.opener = null
    tab.document.title = 'Đang mở HeyStat…'
    tab.document.body.textContent = 'Đang mở bộ dữ liệu trong HeyStat…'
  } catch {
    // The placeholder text is cosmetic; the navigation below still works.
  }
  try {
    const res = await api.post(`/classes/${classId}/files/${fileId}/open-url`)
    const name: string = res.data.filename ?? fallbackName
    const fileUrl = encodeURIComponent(`${window.location.origin}/api/v1/files/ot/${res.data.token}`)
    if (!tab.closed) tab.location.replace(`${window.location.origin}/#open?url=${fileUrl}&title=${encodeURIComponent(name)}`)
  } catch (e) {
    tab.close()
    throw e
  }
}
