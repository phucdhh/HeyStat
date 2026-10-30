import api from '@/api/client'

/**
 * The export endpoints are Bearer-authenticated, so `window.open()` on their URL only ever
 * returns a 401; fetch the blob through the api client and hand it to the browser instead.
 */
export async function downloadFile(path: string, fallbackName: string) {
  const res = await api.get(path, { responseType: 'blob' })
  const name = /filename="?([^";]+)"?/.exec(res.headers['content-disposition'] ?? '')?.[1] || fallbackName
  const url = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
