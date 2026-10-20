/**
 * Drive an embedded HeyStat (jamovi) session from the LMS, without touching the
 * jamovi client: the browser clones the dataset, hands it to /open, and later
 * tells jamovi to save into {{Temp}} and downloads that file back again.
 */
import { ref } from 'vue'
import api from '@/api/client'

export interface SessionTokenResponse {
  embed_url: string
  session_token: string
  collab_role: string
  session_path: string
  assignment_id: string
  session_query: string
  dataset: { file_name: string; download_url: string } | null
}

async function lastJsonLine(resp: Response): Promise<any> {
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  const text = (await resp.text()).trim()
  const lines = text.split('\n')
  return JSON.parse(lines[lines.length - 1])
}

function escapeHtml(text: string) {
  return text.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string)
}

export interface Capture {
  blob: Blob
  report: string
}

export function useJamoviSession() {
  const session = ref<SessionTokenResponse | null>(null)
  const instanceId = ref<string | null>(null)
  const embedUrl = ref<string | null>(null)
  const captureName = ref('')
  const error = ref('')
  const starting = ref(false)
  const capturing = ref(false)
  const lastAutoSave = ref<Date | null>(null)
  const frameEl = ref<HTMLIFrameElement | null>(null)

  async function start(assignmentId: string) {
    starting.value = true
    error.value = ''
    try {
      const { data } = await api.post<SessionTokenResponse>('/sessions/token', { assignment_id: assignmentId })
      session.value = data

      if (!data.dataset) {
        // No dataset attached: jamovi starts blank, so there is nothing to name
        // the capture file after and the student submits from "Tệp của tôi".
        embedUrl.value = `${window.location.origin}${data.embed_url}`
        return
      }

      const token = localStorage.getItem('access_token')
      const blobResp = await fetch(data.dataset.download_url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!blobResp.ok) throw new Error(`Không tải được bộ dữ liệu (HTTP ${blobResp.status})`)
      const blob = await blobResp.blob()

      const form = new FormData()
      form.append('file', blob, data.dataset.file_name)
      const opened = await lastJsonLine(await fetch('/open', { method: 'POST', body: form }))
      if (opened.status !== 'OK' || !opened.url) throw new Error(opened.message || 'HeyStat không mở được phiên làm việc')

      const url = opened.url.startsWith('/') ? opened.url : `/${opened.url}`
      instanceId.value = url.replace(/\/+$/, '').split('/').pop() || null
      embedUrl.value = `${window.location.origin}${url}?${data.session_query}`
      captureName.value = data.dataset.file_name
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e?.message ?? 'Không thể khởi động phiên HeyStat'
    } finally {
      starting.value = false
    }
  }

  /** Ask jamovi to write its current state into {{Temp}} and fetch it back. */
  async function capture(): Promise<Capture> {
    if (!instanceId.value) throw new Error('Phiên HeyStat chưa sẵn sàng')
    capturing.value = true
    try {
      const name = captureName.value || `Dataset_${(session.value?.assignment_id ?? '').slice(0, 8)}.omv`
      const options = { path: `{{Temp}}/${name.replace(/\.omv$/i, '')}.omv`, export: true }
      const form = new FormData()
      form.append('options', JSON.stringify(options))
      const saved = await lastJsonLine(await fetch(`/${instanceId.value}/save`, { method: 'POST', body: form }))
      if (saved.status !== 'OK') throw new Error(saved.message || 'HeyStat không lưu được phiên')

      const source = saved.filename || String(saved.path).split('/').pop()
      const fileResp = await fetch(`/${instanceId.value}/dl/${encodeURIComponent(source)}`)
      if (!fileResp.ok) throw new Error(`Không lấy được file (.omv) từ HeyStat (HTTP ${fileResp.status})`)
      return { blob: await fileResp.blob(), report: captureReport() }
    } finally {
      capturing.value = false
    }
  }

  /** Collect the tables jamovi rendered in the student's browser.
   *
   * The submitted .omv is what the grader reads — it carries the analysis results as
   * protobuf, so these iframes are only a fallback for analyses the server had not
   * run yet at save time. Each box is one analysis: its first heading names the
   * analysis, and the rest are sub-group titles that must not be mistaken for one
   * (jamovi reuses <h1> for those). */
  function captureReport(): string {
    const outer = frameEl.value?.contentDocument
    if (!outer) return ''
    const chunks: string[] = []
    for (const box of Array.from(outer.querySelectorAll('div.jmv-results-container'))) {
      if (box.classList.contains('empty-analysis')) continue
      const doc = (box.querySelector('iframe.analysis') as HTMLIFrameElement | null)?.contentDocument
      if (!doc) continue
      const cells = Array.from(doc.querySelectorAll('table'))
      if (!cells.length) continue
      const name = (doc.querySelector('h1')?.textContent ?? box.getAttribute('data-analysis-name') ?? '').trim()
      chunks.push(`<h1>${escapeHtml(name)}</h1>${cells.map((el) => el.outerHTML).join('')}`)
    }
    return chunks.join('')
  }

  async function stop() {
    const token = session.value?.session_token
    if (!token) return
    session.value = null
    try {
      await api.delete('/sessions/token', { data: { session_token: token } })
    } catch {}
  }

  return {
    session, instanceId, embedUrl, captureName, error, starting, capturing, lastAutoSave, frameEl,
    start, capture, captureReport, stop,
  }
}
