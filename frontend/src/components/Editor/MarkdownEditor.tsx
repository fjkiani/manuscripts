import React from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from 'codemirror'

interface MarkdownEditorProps {
  content: string
  onChange: (value: string) => void
  darkMode?: boolean
}

const lightTheme = EditorView.theme({
  '&': {
    height: '100%',
    fontSize: '13px',
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
  },
  '.cm-content': {
    padding: '1.5rem 2rem',
    minHeight: '100%',
    caretColor: '#0ea5e9',
  },
  '.cm-line': {
    lineHeight: '1.7',
  },
  '.cm-focused': {
    outline: 'none',
  },
  '.cm-editor': {
    height: '100%',
  },
  '.cm-scroller': {
    overflow: 'auto',
  },
})

export function MarkdownEditor({ content, onChange, darkMode = false }: MarkdownEditorProps) {
  return (
    <div className="h-full overflow-hidden">
      <CodeMirror
        value={content}
        height="100%"
        extensions={[
          markdown(),
          lightTheme,
        ]}
        theme={darkMode ? oneDark : 'light'}
        onChange={onChange}
        basicSetup={{
          lineNumbers: false,
          foldGutter: false,
          dropCursor: true,
          allowMultipleSelections: true,
          indentOnInput: true,
          bracketMatching: true,
          closeBrackets: true,
          autocompletion: false,
          rectangularSelection: true,
          crosshairCursor: false,
          highlightActiveLine: true,
          highlightSelectionMatches: true,
          closeBracketsKeymap: true,
          searchKeymap: true,
          foldKeymap: false,
          completionKeymap: false,
          lintKeymap: false,
        }}
        placeholder="# Your Manuscript Title

## Abstract

Write your abstract here...

## 1. Introduction

Start writing your introduction...

## References

[1] Author, A. (Year). Title. Journal, Vol(Issue), Pages."
      />
    </div>
  )
}
