import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDocument, getUploadStatus } from '../api'
import useStore from '../store/useStore'
import Button from '../components/Button'
import { Upload, File, X } from '../components/Icons'

const PHASES = ['Uploading document...', 'Analyzing content...', 'Extracting key concepts...', 'Generating reels...', 'Finalizing...']

export default function UploadPage() {
  const navigate = useNavigate()
  const fileRef = useRef(null)
  const pollRef = useRef(null)
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [phase, setPhase] = useState(0)
  const [error, setError] = useState(null)
  const { setUploadStatus, clearUpload } = useStore()

  const handleFile = (f) => {
    if (f && (f.type === 'application/pdf' || f.name.endsWith('.docx'))) {
      setFile(f)
      setError(null)
    }
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    handleFile(f)
  }, [])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const pollStatus = (uploadId) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await getUploadStatus(uploadId)
        const p = status.progress || 0
        setProgress(p)
        setPhase(Math.min(Math.floor(p / 20), PHASES.length - 1))
        setUploadStatus({ id: uploadId, status: status.status, progress: p })

        if (status.status === 'done' || p >= 100) {
          clearInterval(pollRef.current)
          setProgress(100)
          setTimeout(() => {
            clearUpload()
            navigate('/')
          }, 600)
        } else if (status.status === 'error') {
          clearInterval(pollRef.current)
          setError('Processing failed. Please try again.')
          setProcessing(false)
        }
      } catch {
        // Keep polling on transient errors
      }
    }, 3000)
  }

  const startProcessing = async () => {
    setProcessing(true)
    setProgress(0)
    setPhase(0)
    setError(null)

    try {
      const data = await uploadDocument(file)
      setUploadStatus({ id: data.upload_id, status: 'processing', progress: 0 })
      pollStatus(data.upload_id)
    } catch {
      // API not available — fall back to simulated progress
      simulateProgress()
    }
  }

  // Fallback simulated progress when backend is unavailable
  const simulateProgress = () => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        const next = prev + 2
        if (next >= 100) {
          clearInterval(interval)
          setTimeout(() => navigate('/'), 600)
          return 100
        }
        setPhase(Math.min(Math.floor(next / 20), PHASES.length - 1))
        return next
      })
    }, 80)
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1048576).toFixed(1) + ' MB'
  }

  if (processing) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-6 fade-up">
        {/* Progress ring */}
        <div className="relative w-48 h-48 mb-8">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(99,102,241,0.1)" strokeWidth="6" />
            <circle
              cx="50" cy="50" r="42" fill="none"
              stroke="url(#progressGrad)" strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={`${progress * 2.64} 264`}
              className="transition-all duration-200"
            />
            <defs>
              <linearGradient id="progressGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#6366F1" />
                <stop offset="100%" stopColor="#818CF8" />
              </linearGradient>
            </defs>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold font-display">{progress}%</span>
            <span className="text-text-muted text-xs">Processing</span>
          </div>
        </div>

        <p className="text-text-secondary text-sm font-medium mb-2 progress-pulse">
          {PHASES[phase]}
        </p>

        <p className="text-text-muted text-xs">
          Batch {Math.min(Math.floor(progress / 20) + 1, 5)} / 5
        </p>

        {/* Animated dots */}
        <div className="flex gap-1.5 mt-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-primary pulse-3"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto p-6 pt-10 fade-up">
      <h1 className="text-2xl font-bold font-display mb-1">Upload Document</h1>
      <p className="text-text-muted text-sm mb-8">Transform your documents into bite-sized learning reels</p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/10 text-danger text-sm">
          {error}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ${
          dragOver
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-border hover:border-primary/30 hover:bg-surface-alt/50'
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          onChange={(e) => handleFile(e.target.files[0])}
        />
        <div className="flex justify-center mb-4 text-text-muted">
          <Upload />
        </div>
        <p className="font-semibold mb-1">Drag & drop your file here</p>
        <p className="text-text-muted text-sm">or click to browse</p>
        <p className="text-text-muted text-xs mt-3">PDF, DOCX up to 50 MB</p>
      </div>

      {/* Selected file */}
      {file && (
        <div className="mt-6 flex items-center gap-3 p-4 bg-surface rounded-xl border border-border scale-in">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
            <File />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{file.name}</p>
            <p className="text-text-muted text-xs">{formatSize(file.size)}</p>
          </div>
          <button onClick={() => setFile(null)} className="text-text-muted hover:text-danger cursor-pointer">
            <X />
          </button>
        </div>
      )}

      {/* Generate button */}
      {file && (
        <Button full onClick={startProcessing} className="mt-6">
          Generate Reels
        </Button>
      )}

      {/* Recent uploads */}
      <div className="mt-12">
        <h3 className="text-sm font-semibold text-text-muted mb-4">Recent Uploads</h3>
        {['Deep Learning Fundamentals.pdf', 'NLP Research Paper.pdf'].map((name, i) => (
          <div key={i} className="flex items-center gap-3 p-3 rounded-lg hover:bg-surface-alt/50 transition-colors">
            <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center text-primary">
              <File />
            </div>
            <div className="flex-1">
              <p className="text-sm">{name}</p>
              <p className="text-text-muted text-xs">{i === 0 ? '5 reels generated' : '3 reels generated'}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
