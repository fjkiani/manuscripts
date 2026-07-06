import React from 'react'
import { ChevronDown } from 'lucide-react'
import { JOURNAL_STYLES } from '../../api/client'

interface StyleSelectorProps {
  value: string
  onChange: (style: string) => void
}

export function StyleSelector({ value, onChange }: StyleSelectorProps) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg pl-3 pr-8 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer hover:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-colors"
        title="Select journal style"
      >
        {JOURNAL_STYLES.map(style => (
          <option key={style.id} value={style.id}>
            {style.name}
          </option>
        ))}
      </select>
      <ChevronDown
        size={14}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
      />
    </div>
  )
}
