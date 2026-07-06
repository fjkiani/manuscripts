import React, { useEffect, useRef, useState, useCallback } from 'react'
import { getPreview } from '../../api/client'
import { RefreshCw } from 'lucide-react'

interface PreviewPaneProps {
  content: string
  style: string
  editorMode: 'rich' | 'markdown'
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debouncedValue
}

export function PreviewPane({ content, style, editorMode }: PreviewPaneProps) {
  const [html, setHtml] = useState('')
  const [loading, setLoading] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const debouncedContent = useDebounce(content, 500)
  const debouncedStyle = useDebounce(style, 300)

  const fetchPreview = useCallback(async () => {
    if (!debouncedContent.trim()) {
      setHtml('<div style="padding:2rem;color:#999;font-family:serif;">Start writing to see a preview...</div>')
      return
    }

    setLoading(true)
    try {
      // For rich text mode, strip HTML tags for the preview API
      const textContent = editorMode === 'rich'
        ? debouncedContent.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
        : debouncedContent

      const previewHtml = await getPreview(textContent, debouncedStyle)
      setHtml(previewHtml)
    } catch {
      // Fallback: render content directly
      setHtml(`<div style="padding:2rem;font-family:'Times New Roman',serif;font-size:11pt;line-height:1.5;">${
        editorMode === 'rich' ? debouncedContent : debouncedContent.replace(/\n/g, '<br>')
      }</div>`)
    } finally {
      setLoading(false)
    }
  }, [debouncedContent, debouncedStyle, editorMode])

  useEffect(() => {
    fetchPreview()
  }, [fetchPreview])

  // Write HTML to iframe for isolated rendering
  useEffect(() => {
    if (iframeRef.current && html) {
      const doc = iframeRef.current.contentDocument
      if (doc) {
        doc.open()
        doc.write(html)
        doc.close()
      }
    }
  }, [html])

  return (
    <div className="flex flex-col h-full bg-gray-100 dark:bg-gray-900">
      {/* Preview header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
          Preview
        </span>
        {loading && (
          <RefreshCw size={14} className="text-gray-400 animate-spin" />
        )}
      </div>

      {/* Preview content */}
      <div className="flex-1 overflow-hidden p-4">
        <div className="h-full bg-white shadow-sm rounded border border-gray-200 dark:border-gray-700 overflow-hidden">
          <iframe
            ref={iframeRef}
            className="w-full h-full border-0"
            title="Manuscript Preview"
            sandbox="allow-same-origin"
          />
        </div>
      </div>
    </div>
  )
}
