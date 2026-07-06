import { useEffect, useRef } from 'react'

const AUTOSAVE_KEY = 'manuscripts_autosave'
const AUTOSAVE_INTERVAL = 30_000 // 30 seconds

interface AutosaveData {
  content: string
  style: string
  editorMode: 'rich' | 'markdown'
  savedAt: string
}

export function useAutosave(content: string, style: string, editorMode: 'rich' | 'markdown') {
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    timerRef.current = setInterval(() => {
      const data: AutosaveData = {
        content,
        style,
        editorMode,
        savedAt: new Date().toISOString(),
      }
      try {
        localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(data))
      } catch {
        // localStorage full or unavailable — ignore
      }
    }, AUTOSAVE_INTERVAL)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [content, style, editorMode])
}

export function loadAutosave(): AutosaveData | null {
  try {
    const raw = localStorage.getItem(AUTOSAVE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as AutosaveData
  } catch {
    return null
  }
}

export function clearAutosave() {
  localStorage.removeItem(AUTOSAVE_KEY)
}
