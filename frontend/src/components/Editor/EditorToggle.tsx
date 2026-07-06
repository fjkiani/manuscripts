import React from 'react'
import { Type, Code2 } from 'lucide-react'

interface EditorToggleProps {
  mode: 'rich' | 'markdown'
  onChange: (mode: 'rich' | 'markdown') => void
}

export function EditorToggle({ mode, onChange }: EditorToggleProps) {
  return (
    <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1 gap-1">
      <button
        onClick={() => onChange('rich')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
          mode === 'rich'
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
        }`}
        title="Rich text editor (WYSIWYG)"
      >
        <Type size={14} />
        <span>Rich Text</span>
      </button>
      <button
        onClick={() => onChange('markdown')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
          mode === 'markdown'
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
        }`}
        title="Markdown editor with live preview"
      >
        <Code2 size={14} />
        <span>Markdown</span>
      </button>
    </div>
  )
}
