import { useState, useEffect, useRef, useCallback } from 'react'
import { getJobStatus, JobResponse } from '../api/client'

interface UseJobReturn {
  job: JobResponse | null
  isPolling: boolean
  error: string | null
  startPolling: (jobId: string) => void
  stopPolling: () => void
  reset: () => void
}

export function useJob(): UseJobReturn {
  const [job, setJob] = useState<JobResponse | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const jobIdRef = useRef<string | null>(null)

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const poll = useCallback(async (jobId: string) => {
    try {
      const status = await getJobStatus(jobId)
      setJob(status)

      if (status.status === 'done' || status.status === 'error') {
        stopPolling()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get job status')
      stopPolling()
    }
  }, [stopPolling])

  const startPolling = useCallback((jobId: string) => {
    jobIdRef.current = jobId
    setIsPolling(true)
    setError(null)

    // Poll immediately
    poll(jobId)

    // Then every 2 seconds
    intervalRef.current = setInterval(() => {
      poll(jobId)
    }, 2000)
  }, [poll])

  const reset = useCallback(() => {
    stopPolling()
    setJob(null)
    setError(null)
    jobIdRef.current = null
  }, [stopPolling])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  return { job, isPolling, error, startPolling, stopPolling, reset }
}
