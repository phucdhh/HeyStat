/** Quick Help: match a jamovi table column name to a plain-language reading guide. */
import { ref } from 'vue'
import api from '@/api/client'

export interface HelpEntry {
  key: string
  label: string
  aliases: string[]
  what: string
  read: string
  watch: string
  apa: string
}

let cache: HelpEntry[] | null = null
const loading = ref(false)

const normalise = (s: string) =>
  s.toLowerCase().replace(/[’‘]/g, "'").replace(/[–—]/g, '-').replace(/\s+/g, ' ').trim()

export function useHelp() {
  const entries = ref<HelpEntry[]>(cache ?? [])
  const error = ref('')

  async function load() {
    if (cache) { entries.value = cache; return }
    loading.value = true
    try {
      const { data } = await api.get('/help/glossary')
      cache = data.entries
      entries.value = data.entries
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Không tải được hướng dẫn'
    } finally {
      loading.value = false
    }
  }

  /** Short aliases (r, f, p) only match a whole column name; long ones may appear inside it. */
  function match(columnText: string): HelpEntry | null {
    const t = normalise(columnText)
    if (!t) return null
    const list = cache ?? []
    for (const e of list) if (e.aliases.some((a) => normalise(a) === t)) return e
    for (const e of list) {
      if (e.aliases.some((a) => a.length >= 4 && t.includes(normalise(a)))) return e
    }
    return null
  }

  return { entries, error, loading, load, match }
}
