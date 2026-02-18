import { useEffect, useRef } from 'react'
import { getUploadStatus } from '../api'
import { getWsBaseUrl, getAuthToken } from '../api/ws'
import useStore from '../store/useStore'

const STAGE_LABELS = {
  uploading: 'Uploading...',
  parsing: 'Parsing...',
  analyzing: 'Analyzing...',
  extracting: 'Extracting concepts...',
  generating: 'Generating reels...',
  embedding: 'Building knowledge base...',
  done: 'Done!',
}

export default function UploadTracker() {
  const bgUpload = useStore((s) => s.bgUpload)
  const updateBgUpload = useStore((s) => s.updateBgUpload)
  const clearBgUpload = useStore((s) => s.clearBgUpload)
  const wsRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (!bgUpload || bgUpload.status === 'done') return

    const uploadId = bgUpload.id

    const handleUpdate = (progress, stage, status) => {
      updateBgUpload({ progress, stage, status })
      if (status === 'done') {
        cleanup()
        // Auto-clear after a short delay so user sees "Done!"
        setTimeout(() => clearBgUpload(), 2000)
      } else if (status === 'error' || status === 'partial') {
        cleanup()
        setTimeout(() => clearBgUpload(), 4000)
      }
    }

    const cleanup = () => {
      if (wsRef.current) { try { wsRef.current.close() } catch {} wsRef.current = null }
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }

    // Try WebSocket first
    const token = getAuthToken()
    if (token && !wsRef.current && !pollRef.current) {
      try {
        const ws = new WebSocket(`${getWsBaseUrl()}/ws/upload/${uploadId}?token=${token}`)
        wsRef.current = ws

        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data)
            if (msg.type === 'progress') {
              handleUpdate(msg.progress ?? 0, msg.stage || 'uploading', msg.status)
            }
          } catch {}
        }

        ws.onerror = () => {
          ws.close()
          wsRef.current = null
          startPolling(uploadId, handleUpdate)
        }

        ws.onclose = () => { wsRef.current = null }
      } catch {
        startPolling(uploadId, handleUpdate)
      }
    } else if (!wsRef.current && !pollRef.current) {
      startPolling(uploadId, handleUpdate)
    }

    return cleanup
  }, [bgUpload?.id])

  const startPolling = (uploadId, handleUpdate) => {
    pollRef.current = setInterval(async () => {
      try {
        const s = await getUploadStatus(uploadId)
        handleUpdate(s.progress ?? 0, s.stage || 'uploading', s.status)
      } catch {}
    }, 2000)
  }

  if (!bgUpload) return null

  const progress = bgUpload.progress || 0
  const label = STAGE_LABELS[bgUpload.stage] || 'Processing...'
  const isDone = bgUpload.status === 'done'
  const isError = bgUpload.status === 'error' || bgUpload.status === 'partial'

  return (
    <div className={`fixed top-0 left-0 right-0 z-50 md:left-16 ${isDone ? 'bg-green-500/90' : isError ? 'bg-danger/90' : 'bg-primary/90'} text-white px-4 py-2 flex items-center gap-3 text-sm backdrop-blur-sm`}>
      <div className="flex-1 min-w-0">
        <span className="font-medium truncate block">{bgUpload.filename}</span>
        <span className="text-white/80 text-xs">{isError ? 'Processing failed' : label}</span>
      </div>
      {!isDone && !isError && (
        <div className="flex items-center gap-2">
          <div className="w-24 h-1.5 rounded-full bg-white/20 overflow-hidden">
            <div
              className="h-full rounded-full bg-white transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs font-semibold tabular-nums">{Math.round(progress)}%</span>
        </div>
      )}
      {isDone && <span className="text-xs font-semibold">Reels ready!</span>}
      {(isDone || isError) && (
        <button
          onClick={clearBgUpload}
          className="text-white/70 hover:text-white text-lg leading-none cursor-pointer"
        >
          &times;
        </button>
      )}
    </div>
  )
}
