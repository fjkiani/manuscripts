const API_BASE = import.meta.env.VITE_API_URL || ''

export interface JobResponse {
  job_id: string
  status: 'queued' | 'processing' | 'rendering' | 'done' | 'error'
  progress: number
  created_at: string
  updated_at: string
  error?: string
  outputs?: Record<string, string>
}

export interface SubmitJobParams {
  file: File
  style: string
  outputs: string[]
  bibFile?: File
  assetsZip?: File
  imageFiles?: File[]
}

export async function submitJob(params: SubmitJobParams): Promise<{ job_id: string; status: string }> {
  const formData = new FormData()
  formData.append('file', params.file)
  formData.append('style', params.style)
  formData.append('outputs', params.outputs.join(','))
  if (params.bibFile) {
    formData.append('bib_file', params.bibFile)
  }
  if (params.assetsZip) {
    formData.append('assets_zip', params.assetsZip)
  }
  if (params.imageFiles) {
    for (const img of params.imageFiles) {
      formData.append('images', img)
    }
  }

  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

export async function getJobStatus(jobId: string): Promise<JobResponse> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}`)
  if (!response.ok) {
    throw new Error(`Failed to get job status: HTTP ${response.status}`)
  }
  return response.json()
}

export async function getPreview(content: string, style: string): Promise<string> {
  const formData = new FormData()
  formData.append('content', content)
  formData.append('style', style)

  const response = await fetch(`${API_BASE}/api/preview`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) return ''
  const data = await response.json()
  return data.html || ''
}

export function getDownloadUrl(jobId: string, format: string): string {
  return `${API_BASE}/api/files/${jobId}/${format}`
}

export const JOURNAL_STYLES = [
  { id: 'ieee', name: 'IEEE', description: 'Two-column, numbered refs' },
  { id: 'elsevier', name: 'Elsevier', description: 'Single-column, numbered refs' },
  { id: 'springer', name: 'Springer LNCS', description: 'Numbered refs, Springer style' },
  { id: 'apa', name: 'APA 7th', description: 'Author-date citations' },
  { id: 'ama', name: 'AMA 11th', description: 'Superscript numbered citations' },
  { id: 'generic', name: 'Generic', description: 'Clean publication-ready style' },
  { id: 'biorxiv', name: 'bioRxiv Preprint', description: 'Pandoc + tectonic pipeline for bioRxiv' },
  { id: 'crispro', name: 'CrisPRO Preprint', description: 'A4, booktabs, "For Research Use Only" footer' },
  { id: 'preprint', name: 'Generic Preprint', description: 'A4, booktabs, no branding' },
] as const

export const OUTPUT_FORMATS = [
  { id: 'pdf', name: 'PDF', icon: '📄', description: 'Publication-ready PDF via XeLaTeX' },
  { id: 'docx', name: 'Word', icon: '📝', description: 'Editable DOCX with journal styles' },
  { id: 'latex', name: 'LaTeX', icon: '🔤', description: 'LaTeX source (.tex)' },
  { id: 'html', name: 'HTML', icon: '🌐', description: 'Styled HTML document' },
] as const
