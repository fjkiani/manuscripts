import React, { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, X } from 'lucide-react'

interface DropZoneProps {
  onFileAccepted: (file: File) => void
  onBibFileAccepted?: (file: File) => void
  onAssetsZipAccepted?: (file: File) => void
  currentFile: File | null
  currentBibFile: File | null
  currentAssetsZip: File | null
  onClearFile: () => void
  onClearBibFile: () => void
  onClearAssetsZip: () => void
}

const ACCEPTED_TYPES = {
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/markdown': ['.md'],
  'text/plain': ['.txt'],
  'application/x-tex': ['.tex'],
  'application/zip': ['.zip'],
}

const BIB_TYPES = {
  'application/x-bibtex': ['.bib'],
  'text/plain': ['.ris'],
}

function FileChip({ file, onClear, label }: { file: File; onClear: () => void; label?: string }) {
  const sizeKB = (file.size / 1024).toFixed(1)
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-brand-50 dark:bg-brand-900/30 border border-brand-200 dark:border-brand-800 rounded-lg">
      <FileText size={14} className="text-brand-600 dark:text-brand-400 flex-shrink-0" />
      <div className="min-w-0 flex-1">
        {label && <p className="text-xs text-brand-500 dark:text-brand-400">{label}</p>}
        <p className="text-sm font-medium text-brand-700 dark:text-brand-300 truncate">{file.name}</p>
        <p className="text-xs text-brand-500 dark:text-brand-400">{sizeKB} KB</p>
      </div>
      <button
        onClick={onClear}
        className="text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 flex-shrink-0"
        title="Remove file"
      >
        <X size={14} />
      </button>
    </div>
  )
}

export function DropZone({
  onFileAccepted,
  onBibFileAccepted,
  onAssetsZipAccepted,
  currentFile,
  currentBibFile,
  currentAssetsZip,
  onClearFile,
  onClearBibFile,
  onClearAssetsZip,
}: DropZoneProps) {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return
    const file = acceptedFiles[0]
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (ext === 'bib' || ext === 'ris') {
      onBibFileAccepted?.(file)
    } else if (ext === 'zip') {
      onAssetsZipAccepted?.(file)
    } else {
      onFileAccepted(file)
    }
  }, [onFileAccepted, onBibFileAccepted, onAssetsZipAccepted])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { ...ACCEPTED_TYPES, ...BIB_TYPES },
    maxFiles: 2,
    maxSize: 50 * 1024 * 1024,
  })

  return (
    <div className="flex flex-col gap-2">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-brand-400 bg-brand-50 dark:bg-brand-900/20'
            : 'border-gray-200 dark:border-gray-700 hover:border-brand-300 dark:hover:border-brand-700 hover:bg-gray-50 dark:hover:bg-gray-800/50'
        }`}
      >
        <input {...getInputProps()} />
        <Upload size={20} className={`mx-auto mb-2 ${isDragActive ? 'text-brand-500' : 'text-gray-400'}`} />
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {isDragActive ? 'Drop your file here' : 'Drop manuscript or click to browse'}
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          .docx · .md · .tex · .txt · .bib · .ris · .zip
        </p>
      </div>

      {currentFile && (
        <FileChip file={currentFile} onClear={onClearFile} label="Manuscript" />
      )}
      {currentBibFile && (
        <FileChip file={currentBibFile} onClear={onClearBibFile} label="Bibliography" />
      )}
      {currentAssetsZip && (
        <FileChip file={currentAssetsZip} onClear={onClearAssetsZip} label="Assets bundle (.zip)" />
      )}
    </div>
  )
}
