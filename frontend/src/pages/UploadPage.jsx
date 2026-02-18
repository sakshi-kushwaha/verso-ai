import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDocument, getUploads } from '../api'
import useStore from '../store/useStore'
import Button from '../components/Button'
import { Upload, File, X } from '../components/Icons'

export default function UploadPage() {
  const navigate = useNavigate()
  const fileRef = useRef(null)
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [recentUploads, setRecentUploads] = useState([])
  const setBgUpload = useStore((s) => s.setBgUpload)
  const bgUpload = useStore((s) => s.bgUpload)
  const isProcessing = bgUpload && bgUpload.status !== 'done'

  useEffect(() => {
    getUploads().then((uploads) => setRecentUploads(uploads.filter(u => u.status === 'done'))).catch(() => {})
  }, [])

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

  const startProcessing = async () => {
    setUploading(true)
    setError(null)

    try {
      const data = await uploadDocument(file)
      const id = data.id || data.upload_id
      // Hand off to global background tracker and navigate away
      setBgUpload({ id, filename: file.name, progress: 0, stage: 'uploading', status: 'processing' })
      setFile(null)
      navigate('/')
    } catch {
      setError('Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1048576).toFixed(1) + ' MB'
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

      {/* Currently processing banner */}
      {isProcessing && (
        <div className="bg-surface rounded-2xl p-6 border border-primary/30 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
              <File />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">{bgUpload.filename}</p>
              <p className="text-primary text-xs">
                {bgUpload.stage === 'uploading' ? 'Uploading...' :
                 bgUpload.stage === 'parsing' ? 'Parsing document...' :
                 bgUpload.stage === 'analyzing' ? 'Analyzing content...' :
                 bgUpload.stage === 'extracting' ? 'Extracting concepts...' :
                 bgUpload.stage === 'generating' ? 'Generating reels...' :
                 bgUpload.stage === 'embedding' ? 'Building knowledge base...' :
                 'Processing...'}
              </p>
            </div>
            <span className="text-sm font-bold text-primary tabular-nums">{Math.round(bgUpload.progress || 0)}%</span>
          </div>
          <div className="h-2 rounded-full bg-surface-alt overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${bgUpload.progress || 0}%` }}
            />
          </div>
          <p className="text-text-muted text-xs mt-3 text-center">Please wait for processing to finish before uploading another document</p>
        </div>
      )}

      {/* Drop zone */}
      {!isProcessing && (
        <>
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
            <Button full onClick={startProcessing} disabled={uploading} className="mt-6">
              {uploading ? 'Uploading...' : 'Generate Reels'}
            </Button>
          )}
        </>
      )}

      {/* Recent uploads */}
      {recentUploads.length > 0 && (
        <div className="mt-12">
          <h3 className="text-sm font-semibold text-text-muted mb-4">Recent Uploads</h3>
          {recentUploads.map((upload) => (
            <div key={upload.id} className="flex items-center gap-3 p-3 rounded-lg hover:bg-surface-alt/50 transition-colors">
              <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center text-primary">
                <File />
              </div>
              <div className="flex-1">
                <p className="text-sm">{upload.filename}</p>
                <p className="text-text-muted text-xs">{upload.status === 'done' ? 'Completed' : upload.status}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
