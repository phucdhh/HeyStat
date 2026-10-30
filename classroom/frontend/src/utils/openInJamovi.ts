import api from '@/api/client'

/**
 * Opens a class file in the HeyStat editor. The API hands back a one-time token for the
 * file; the jamovi client reads it from its hash route, so the URL shape stays as-is.
 */
export async function openClassFileInJamovi(classId: string, fileId: string, fallbackName: string) {
  const res = await api.post(`/classes/${classId}/files/${fileId}/open-url`)
  const name: string = res.data.filename ?? fallbackName
  const fileUrl = encodeURIComponent(`${window.location.origin}/api/v1/files/ot/${res.data.token}`)
  window.open(`${window.location.origin}/#open?url=${fileUrl}&title=${encodeURIComponent(name)}`, '_blank')
}
