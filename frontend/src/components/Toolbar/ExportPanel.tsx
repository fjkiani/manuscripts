import React, { useState } from 'react'
import { Download, Loader2, CheckCircle, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { submitJob, getDownloadUrl, OUTPUT_FORMATS } from '../../api/client'
import { useJob } from '../../hooks/useJob'

interface ExportPanelProps {
  content: string
  style: string
  editorMode: 'rich' | 'markdown'
  uploadedFile: File | null
  bibFile: File | null
  assetsZip: File | null
}

export function ExportPanel({ content, style, editorMode, uploadedFile, bibFile, assetsZip }: ExportPanelProps) {
  const [selectedFormats, setSelectedFormats] = useState<Set<string>>(new Set(['pdf', 'docx']))
  const { job, isPolling, error, startPolling, reset } = useJob()

  const toggleFormat = (fmt: string) => {
    setSelectedFormats(prev => {
      const next = new Set(prev)
      if (next.has(fmt)) {
        if (next.size > 1) next.delete(fmt) // keep at least one
      } else {
        next.add(fmt)
      }
      return next
    })
  }

  const handleExport = async () => {
    if (selectedFormats.size === 0) {
      toast.error('Select at least one output format')
      return
    }

    // Create a file from editor content if no file was uploaded
    let fileToSubmit = uploadedFile
    if (!fileToSubmit) {
      const ext = editorMode === 'rich' ? '.html' : '.md'
      const mimeType = editorMode === 'rich' ? 'text/html' : 'text/markdown'
      fileToSubmit = new File([content], `manuscript${ext}`, { type: mimeType })
    }

    reset()

    try {
      const result = await submitJob({
        file: fileToSubmit,
        style,
        outputs: Array.from(selectedFormats),
        bibFile: bibFile || undefined,
        assetsZip: assetsZip || undefined,
      })
      startPolling(result.job_id)
      toast.success('Job submitted! Processing your manuscript...')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to submit job')
    }
  }

  const handleDownload = (format: string) => {
    if (!job?.job_id) return
    const url = getDownloadUrl(job.job_id, format)
    const a = document.createElement('a')
    a.href = url
    a.download = `manuscript_formatted.${format === 'latex' ? 'tex' : format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const statusColor = {
    queued: 'text-yellow-600',
    processing: 'text-blue-600',
    rendering: 'text-purple-600',
    done: 'text-green-600',
    error: 'text-red-600',
  }

  const statusLabel = {
    queued: 'Queued...',
    processing: 'Processing manuscript...',
    rendering: 'Rendering outputs...',
    done: 'Done!',
    error: 'Error',
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Format selection */}
      <div>
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
          Output Formats
        </p>
        <div className="flex flex-wrap gap-2">
          {OUTPUT_FORMATS.map(fmt => (
            <button
              key={fmt.id}
              onClick={() => toggleFormat(fmt.id)}
              title={fmt.description}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                selectedFormats.has(fmt.id)
                  ? 'bg-brand-50 dark:bg-brand-900/30 border-brand-300 dark:border-brand-700 text-brand-700 dark:text-brand-300'
                  : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-gray-300'
              }`}
            >
              <span>{fmt.icon}</span>
              <span>{fmt.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Export button */}
      <button
        onClick={handleExport}
        disabled={isPolling}
        className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg font-medium text-sm transition-colors"
      >
        {isPolling ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            <span>Processing...</span>
          </>
        ) : (
          <>
            <Download size={16} />
            <span>Export Manuscript</span>
          </>
        )}
      </button>

      {/* Job status */}
      {job && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center gap-2 mb-2">
            {job.status === 'done' ? (
              <CheckCircle size={16} className="text-green-500" />
            ) : job.status === 'error' ? (
              <XCircle size={16} className="text-red-500" />
            ) : (
              <Loader2 size={16} className={`animate-spin ${statusColor[job.status]}`} />
            )}
            <span className={`text-sm font-medium ${statusColor[job.status]}`}>
              {statusLabel[job.status]}
            </span>
          </div>

          {/* Progress bar */}
          {job.status !== 'done' && job.status !== 'error' && (
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mb-2">
              <div
                className="bg-brand-500 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${job.progress}%` }}
              />
            </div>
          )}

          {/* Error message */}
          {job.status === 'error' && job.error && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">{job.error}</p>
          )}

          {/* Download buttons */}
          {job.status === 'done' && job.outputs && (
            <div className="flex flex-wrap gap-2 mt-2">
              {Object.keys(job.outputs).map(fmt => {
                const fmtInfo = OUTPUT_FORMATS.find(f => f.id === fmt)
                return (
                  <button
                    key={fmt}
                    onClick={() => handleDownload(fmt)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 rounded-lg text-sm font-medium hover:bg-green-100 transition-colors"
                  >
                    <Download size={13} />
                    <span>{fmtInfo?.name || fmt.toUpperCase()}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  )
}
