import React, { useState, useCallback, useEffect } from 'react'
import { Toaster } from 'react-hot-toast'
import { Moon, Sun, BookOpen, PanelRight, PanelRightClose } from 'lucide-react'

import { RichTextEditor } from './components/Editor/RichTextEditor'
import { MarkdownEditor } from './components/Editor/MarkdownEditor'
import { EditorToggle } from './components/Editor/EditorToggle'
import { PreviewPane } from './components/Preview/PreviewPane'
import { StyleSelector } from './components/Toolbar/StyleSelector'
import { ExportPanel } from './components/Toolbar/ExportPanel'
import { DropZone } from './components/Upload/DropZone'
import { useAutosave, loadAutosave } from './hooks/useAutosave'

const SAMPLE_CONTENT = `# The Impact of Machine Learning on Scientific Discovery

## Abstract

This paper examines the transformative role of machine learning (ML) in accelerating scientific discovery across multiple disciplines. We review recent advances in ML-driven hypothesis generation, experimental design, and data analysis, demonstrating significant improvements in research efficiency and discovery rates.

**Keywords:** machine learning, scientific discovery, artificial intelligence, research methodology

## 1. Introduction

The integration of machine learning into scientific research has fundamentally altered the pace and nature of discovery [1]. Traditional hypothesis-driven research, while rigorous, is constrained by human cognitive limitations in processing large datasets and identifying complex patterns [2].

Recent developments in deep learning, reinforcement learning, and large language models have opened new avenues for automated hypothesis generation and experimental optimization [3, 4].

## 2. Methods

### 2.1 Data Collection

We analyzed 1,247 peer-reviewed publications from 2018–2024 that explicitly reported ML-assisted discoveries. Publications were sourced from PubMed, arXiv, and Web of Science using systematic search protocols.

### 2.2 Analysis Framework

Each publication was evaluated across five dimensions: (1) discovery type, (2) ML methodology employed, (3) validation approach, (4) reproducibility metrics, and (5) downstream impact.

## 3. Results

Our analysis revealed that ML-assisted research demonstrated a 3.2-fold increase in discovery rate compared to traditional methods (p < 0.001). Furthermore, 78% of ML-assisted discoveries were independently validated within 18 months of publication.

| Metric | Traditional | ML-Assisted | Improvement |
|--------|-------------|-------------|-------------|
| Discovery rate | 1.0x | 3.2x | +220% |
| Validation time | 36 months | 18 months | -50% |
| False positive rate | 12% | 4% | -67% |

## 4. Discussion

The results suggest that ML integration represents a paradigm shift in scientific methodology. However, several challenges remain, including interpretability of ML models, data quality requirements, and the need for domain expertise in model design.

## 5. Conclusion

Machine learning has demonstrably accelerated scientific discovery. Future work should focus on developing standardized frameworks for ML integration in research workflows.

## References

[1] LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. Nature, 521(7553), 436–444. https://doi.org/10.1038/nature14539

[2] Jumper, J., Evans, R., Pritzel, A., et al. (2021). Highly accurate protein structure prediction with AlphaFold. Nature, 596(7873), 583–589. https://doi.org/10.1038/s41586-021-03819-2

[3] Brown, T., Mann, B., Ryder, N., et al. (2020). Language models are few-shot learners. Advances in Neural Information Processing Systems, 33, 1877–1901.

[4] Senior, A. W., Evans, R., Jumper, J., et al. (2020). Improved protein structure prediction using potentials from deep learning. Nature, 577(7792), 706–710.`

export default function App() {
  const [editorMode, setEditorMode] = useState<'rich' | 'markdown'>('markdown')
  const [content, setContent] = useState(SAMPLE_CONTENT)
  const [style, setStyle] = useState('generic')
  const [darkMode, setDarkMode] = useState(false)
  const [showPreview, setShowPreview] = useState(true)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [bibFile, setBibFile] = useState<File | null>(null)
  const [assetsZip, setAssetsZip] = useState<File | null>(null)

  // Load autosave on mount
  useEffect(() => {
    const saved = loadAutosave()
    if (saved && saved.content) {
      setContent(saved.content)
      setStyle(saved.style || 'generic')
      setEditorMode(saved.editorMode || 'markdown')
    }
  }, [])

  // Apply dark mode
  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  // Autosave
  useAutosave(content, style, editorMode)

  const handleFileAccepted = useCallback(async (file: File) => {
    setUploadedFile(file)
    // Read file content for editor
    const text = await file.text()
    setContent(text)
  }, [])

  const handleEditorModeChange = useCallback((mode: 'rich' | 'markdown') => {
    setEditorMode(mode)
  }, [])

  return (
    <div className={`flex flex-col h-screen bg-gray-50 dark:bg-gray-950 ${darkMode ? 'dark' : ''}`}>
      <Toaster position="top-right" />

      {/* Top navbar */}
      <header className="flex items-center justify-between px-4 py-2.5 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex-shrink-0 z-20">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center">
            <BookOpen size={15} className="text-white" />
          </div>
          <span className="font-semibold text-gray-900 dark:text-white text-lg tracking-tight">
            manuscripts
          </span>
        </div>

        {/* Center controls */}
        <div className="flex items-center gap-3">
          <EditorToggle mode={editorMode} onChange={handleEditorModeChange} />
          <StyleSelector value={style} onChange={setStyle} />
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPreview(v => !v)}
            className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            title={showPreview ? 'Hide preview' : 'Show preview'}
          >
            {showPreview ? <PanelRightClose size={18} /> : <PanelRight size={18} />}
          </button>
          <button
            onClick={() => setDarkMode(v => !v)}
            className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            title="Toggle dark mode"
          >
            {darkMode ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside className="w-64 flex-shrink-0 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col overflow-y-auto">
          <div className="p-4 flex flex-col gap-5">
            {/* File upload */}
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
                Import File
              </p>
              <DropZone
                onFileAccepted={handleFileAccepted}
                onBibFileAccepted={setBibFile}
                onAssetsZipAccepted={setAssetsZip}
                currentFile={uploadedFile}
                currentBibFile={bibFile}
                currentAssetsZip={assetsZip}
                onClearFile={() => setUploadedFile(null)}
                onClearBibFile={() => setBibFile(null)}
                onClearAssetsZip={() => setAssetsZip(null)}
              />
            </div>

            {/* Export */}
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
                Export
              </p>
              <ExportPanel
                content={content}
                style={style}
                editorMode={editorMode}
                uploadedFile={uploadedFile}
                bibFile={bibFile}
                assetsZip={assetsZip}
              />
            </div>

            {/* Style info */}
            <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3">
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">About this style</p>
              <p className="text-xs text-gray-500 dark:text-gray-500">
                {style === 'ieee' && 'Two-column layout, numbered [N] citations, IEEEtran typography.'}
                {style === 'elsevier' && 'Single-column, numbered references, Times New Roman 12pt.'}
                {style === 'springer' && 'LNCS format, numbered refs, compact Springer layout.'}
                {style === 'apa' && 'APA 7th: double-spaced, author-date citations, hanging indent refs.'}
                {style === 'ama' && 'AMA 11th: superscript citations, Vancouver-style references.'}
                {style === 'generic' && 'Clean publication-ready style, no journal constraints.'}
                {style === 'biorxiv' &&
                  'Pandoc markdown → PDF via tectonic, pandoc-crossref, and citeproc. Upload manuscript.md plus optional assets .zip (FIGURES/, references.bib).'}
              </p>
            </div>
          </div>
        </aside>

        {/* Editor area */}
        <main className="flex-1 flex overflow-hidden">
          {/* Editor */}
          <div className={`flex flex-col overflow-hidden border-r border-gray-200 dark:border-gray-800 ${showPreview ? 'w-1/2' : 'flex-1'}`}>
            <div className="flex-1 overflow-hidden bg-white dark:bg-gray-900">
              {editorMode === 'rich' ? (
                <RichTextEditor content={content} onChange={setContent} />
              ) : (
                <MarkdownEditor content={content} onChange={setContent} darkMode={darkMode} />
              )}
            </div>
          </div>

          {/* Preview pane */}
          {showPreview && (
            <div className="w-1/2 flex-shrink-0 overflow-hidden">
              <PreviewPane content={content} style={style} editorMode={editorMode} />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
