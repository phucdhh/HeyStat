/**
 * Open a class file through the server, which issues its one-time token and
 * redirects into HeyStat. A plain window.open during the click is allowed by
 * Safari; navigating it after an awaited API call was not, which left students
 * on a blank placeholder tab.
 */
export function openClassFileInJamovi(classId: string, fileId: string) {
  const tab = window.open(`/api/v1/classes/${classId}/files/${fileId}/open`, '_blank')
  if (!tab) throw new Error('Trình duyệt đã chặn tab mới. Hãy cho phép cửa sổ bật lên cho HeyStat rồi thử lại.')
}
