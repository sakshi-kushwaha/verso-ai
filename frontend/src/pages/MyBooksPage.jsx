import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getUploads, getUploadStatus, getFeed, getFlashcards, getDocSummary, getSummaryAudio } from '../api'
import api from '../api'
import Button from '../components/Button'
import { File, Upload, ArrowL, ArrowR, Cards, Chat, Volume, Pause, Play, Grid, Sparkle } from '../components/Icons'
import { Spinner, ErrorState, EmptyState } from '../components/StateScreens'
import { STAGE_LABELS } from '../components/UploadTracker'
import { getWsBaseUrl, getAuthToken } from '../api/ws'

const ACCENTS = ['#3B82F6', '#06B6D4', '#F472B6', '#F59E0B', '#10B981', '#8B5CF6']

function useUploadWs(uploadId, { onProgress, onReelReady, onFlashcardReady, onVideoReady, onDone }) {
  const wsRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (!uploadId) return

    const cleanup = () => {
      if (wsRef.current) { try { wsRef.current.close() } catch {} wsRef.current = null }
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }

    const handleMsg = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'progress') {
          onProgress?.(msg.progress ?? 0, msg.stage || 'processing', msg.status)
          if (msg.status === 'done' || msg.status === 'error' || msg.status === 'partial') {
            cleanup()
            onDone?.(msg.status)
          }
        } else if (msg.type === 'reel_ready' && msg.reel) {
          onReelReady?.(msg.reel)
        } else if (msg.type === 'flashcard_ready' && msg.flashcard) {
          onFlashcardReady?.(msg.flashcard)
        } else if (msg.type === 'video_ready' && msg.reel_id) {
          onVideoReady?.(msg.reel_id, msg.video_path)
        }
      } catch {}
    }

    const startPolling = () => {
      pollRef.current = setInterval(() => {
        getUploadStatus(uploadId)
          .then((s) => {
            onProgress?.(s.progress ?? 0, s.stage || 'processing', s.status)
            if (s.status === 'done' || s.status === 'error' || s.status === 'partial') {
              cleanup()
              onDone?.(s.status)
            }
          })
          .catch(() => {})
      }, 3000)
    }

    // Try WebSocket first
    const token = getAuthToken()
    if (token) {
      try {
        const ws = new WebSocket(`${getWsBaseUrl()}/ws/upload/${uploadId}?token=${token}`)
        wsRef.current = ws
        ws.onmessage = handleMsg
        ws.onerror = () => { ws.close(); wsRef.current = null; startPolling() }
        ws.onclose = () => { wsRef.current = null }
      } catch { startPolling() }
    } else {
      startPolling()
    }

    // Initial status fetch
    getUploadStatus(uploadId)
      .then((s) => onProgress?.(s.progress ?? 0, s.stage || 'processing', s.status))
      .catch(() => {})

    return cleanup
  }, [uploadId])
}

function ProcessingCard({ book, onDone, onClick }) {
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('processing')
  const [reelsCount, setReelsCount] = useState(0)

  useUploadWs(book.id, {
    onProgress: (p, s) => { setProgress(p); setStage(s) },
    onReelReady: () => setReelsCount((c) => c + 1),
    onDone: () => { if (onDone) onDone() },
  })

  const label = STAGE_LABELS[stage] || 'Processing...'

  return (
    <div
      onClick={onClick}
      className="bg-surface rounded-xl border border-primary/20 p-4 relative overflow-hidden cursor-pointer hover:border-primary/40 transition-all"
    >
      {/* Shimmer overlay */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/5 to-transparent animate-shimmer pointer-events-none" />

      <div className="relative flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0 relative">
          <Sparkle />
          <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-primary animate-pulse" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm truncate">{book.filename}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
              AI Processing
            </span>
            {reelsCount > 0 && (
              <span className="text-xs text-text-muted">
                <span className="font-semibold text-text">{reelsCount}</span> bites ready
              </span>
            )}
          </div>
        </div>
        <span className="text-sm font-bold text-primary tabular-nums">{Math.round(progress)}%</span>
      </div>

      {/* AI thinking dots + View link */}
      <div className="relative flex items-center gap-2 mt-3 px-1">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>
        <span className="text-xs text-primary/80">{label}</span>
        <span className="ml-auto flex items-center gap-1 text-xs text-primary font-medium">
          View <ArrowR />
        </span>
      </div>

      {/* Progress bar */}
      <div className="relative mt-2 h-1.5 rounded-full bg-surface-alt overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

function BookCard({ book, onClick }) {
  const navigate = useNavigate()
  const statusColors = {
    done: 'bg-success/10 text-success',
    error: 'bg-danger/10 text-danger',
    partial: 'bg-amber-500/10 text-amber-400',
  }
  const statusLabels = {
    done: 'Completed',
    error: 'Failed',
    partial: 'Partial',
  }
  const statusLabel = statusLabels[book.status] || book.status

  return (
    <div
      onClick={onClick}
      className="bg-surface rounded-xl border border-border p-4 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer"
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
          <File />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm truncate">{book.filename}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[book.status] || 'bg-surface-alt text-text-muted'}`}>
              {statusLabel}
            </span>
            {book.doc_type && (
              <span className="text-xs text-text-muted">{book.doc_type}</span>
            )}
          </div>
        </div>
      </div>

      {book.status === 'error' && (
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border">
          <span className="text-xs text-text-muted flex-1">Processing timed out or failed</span>
          <button
            className="text-xs text-primary font-medium hover:opacity-80 transition-opacity"
            onClick={(e) => { e.stopPropagation(); navigate('/upload') }}
          >
            Re-upload
          </button>
        </div>
      )}

      {(book.status === 'done' || book.status === 'partial') && (
        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-border">
          <span className="text-xs text-text-muted">
            <span className="font-semibold text-text">{book.reel_count || 0}</span> bites
          </span>
          <span className="text-xs text-text-muted">
            <span className="font-semibold text-text">{book.flashcard_count || 0}</span> flashcards
          </span>
          {book.total_pages > 0 && (
            <span className="text-xs text-text-muted">
              <span className="font-semibold text-text">{book.total_pages}</span> pages
            </span>
          )}
          <span className="ml-auto flex items-center gap-1 text-xs text-primary font-medium">
            View <ArrowR />
          </span>
        </div>
      )}
    </div>
  )
}

function BookSummary({ bookId, initialSummary }) {
  const [summary, setSummary] = useState(initialSummary || null)
  const [expanded, setExpanded] = useState(false)
  const [summaryLoading, setSummaryLoading] = useState(!initialSummary)
  const [summaryError, setSummaryError] = useState(false)
  const [audioState, setAudioState] = useState('idle')
  const audioRef = useRef(null)

  const fetchSummary = () => {
    setSummaryLoading(true)
    setSummaryError(false)
    getDocSummary(bookId)
      .then(d => {
        setSummary(d.summary)
        setSummaryLoading(false)
      })
      .catch(() => {
        setSummaryError(true)
        setSummaryLoading(false)
      })
  }

  useEffect(() => {
    if (summary) return
    fetchSummary()
  }, [bookId])

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  const handleAudio = async () => {
    if (audioState === 'playing' && audioRef.current) {
      audioRef.current.pause()
      setAudioState('idle')
      return
    }
    if (audioState === 'loading') return

    setAudioState('loading')
    try {
      const url = await getSummaryAudio(bookId)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => setAudioState('idle')
      audio.onerror = () => setAudioState('error')
      await audio.play()
      setAudioState('playing')
    } catch {
      setAudioState('error')
    }
  }

  if (summaryLoading) {
    return (
      <div className="bg-surface rounded-xl border border-border p-4 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-semibold">Summary</span>
        </div>
        <div className="flex gap-1.5 items-center">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0.2s' }} />
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0.4s' }} />
          <span className="text-xs text-text-muted ml-2">Generating summary...</span>
        </div>
      </div>
    )
  }

  if (summaryError) {
    return (
      <div className="bg-surface rounded-xl border border-border p-4 mb-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">Summary</span>
          <button
            onClick={fetchSummary}
            className="text-xs text-primary hover:opacity-80 transition-opacity cursor-pointer font-medium"
          >
            Retry
          </button>
        </div>
        <p className="text-xs text-text-muted mt-2">Summary not available yet. Click retry to try again.</p>
      </div>
    )
  }

  if (!summary) return null

  return (
    <div className="bg-surface rounded-xl border border-border p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold">Summary</span>
        <button
          onClick={handleAudio}
          disabled={audioState === 'loading'}
          className={`flex items-center justify-center w-8 h-8 rounded-lg text-xs font-medium transition-all cursor-pointer
            ${audioState === 'playing'
              ? 'bg-primary text-white'
              : 'bg-surface-alt text-text-muted hover:text-text hover:bg-surface-alt/80'
            }
            ${audioState === 'loading' ? 'opacity-60' : ''}
          `}
        >
          {audioState === 'loading' ? (
            <div className="w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
          ) : audioState === 'playing' ? (
            <Pause />
          ) : (
            <Volume />
          )}
        </button>
      </div>

      <div className="relative">
        <p
          className="text-sm text-text-secondary leading-relaxed overflow-hidden transition-[max-height] duration-300 ease-in-out"
          style={{ maxHeight: expanded ? '500px' : '4.5em' }}
        >
          {summary}
        </p>
        {!expanded && (
          <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-surface to-transparent pointer-events-none" />
        )}
      </div>

      <button
        onClick={() => setExpanded(e => !e)}
        className="mt-2 text-xs text-primary hover:opacity-80 transition-opacity cursor-pointer font-medium"
      >
        {expanded ? 'See less' : 'See more'}
      </button>
    </div>
  )
}

function ReelThumbnail({ reel, accent, onClick }) {
  const videoUrl = reel.video_path ? `${api.defaults.baseURL}/video/${reel.id}` : null
  const bgImage = reel.bg_image ? `${api.defaults.baseURL}/${reel.bg_image}` : null

  return (
    <div
      onClick={onClick}
      className="relative aspect-[9/16] rounded-lg overflow-hidden cursor-pointer group border border-border hover:border-primary/40 transition-all"
    >
      {videoUrl ? (
        <video
          src={videoUrl}
          className="w-full h-full object-cover"
          muted
          preload="metadata"
        />
      ) : bgImage ? (
        <img src={bgImage} className="w-full h-full object-cover" alt="" />
      ) : (
        <div className="w-full h-full flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${accent}22, ${accent}44)` }}>
          <Play />
        </div>
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 p-2">
        <p className="text-white text-[10px] sm:text-xs font-semibold line-clamp-2 leading-tight">{reel.title}</p>
      </div>
      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/20">
        <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-white/90 flex items-center justify-center text-black">
          <Play />
        </div>
      </div>
    </div>
  )
}

function FlashcardItem({ fc, index }) {
  const [flipped, setFlipped] = useState(false)
  const gradients = [
    'from-indigo-500/20 to-purple-500/20',
    'from-pink-500/20 to-rose-500/20',
    'from-emerald-500/20 to-teal-500/20',
    'from-amber-500/20 to-orange-500/20',
    'from-blue-500/20 to-cyan-500/20',
  ]
  const borderColors = [
    'border-indigo-500/30',
    'border-pink-500/30',
    'border-emerald-500/30',
    'border-amber-500/30',
    'border-blue-500/30',
  ]
  const gradient = gradients[index % gradients.length]
  const borderColor = borderColors[index % borderColors.length]

  return (
    <div
      onClick={() => setFlipped(f => !f)}
      className="cursor-pointer"
      style={{ perspective: '1000px' }}
    >
      <div
        className="relative w-full transition-transform duration-500"
        style={{
          transformStyle: 'preserve-3d',
          transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
        }}
      >
        {/* Invisible sizers — stacked via grid so container fits the taller face */}
        <div className="invisible grid [&>*]:col-start-1 [&>*]:row-start-1">
          <div className="p-4 sm:p-5">
            <div className="mb-3"><span className="text-xs">Q</span></div>
            <p className="text-sm leading-relaxed">{fc.question}</p>
            <div className="mt-3"><span className="text-xs">Tap</span></div>
          </div>
          <div className="p-4 sm:p-5">
            <div className="mb-3"><span className="text-xs">A</span></div>
            <p className="text-sm leading-relaxed">{fc.answer}</p>
            <div className="mt-3"><span className="text-xs">Tap</span></div>
          </div>
        </div>

        {/* Front — Question */}
        <div
          className={`absolute inset-0 rounded-xl border ${borderColor} p-4 sm:p-5 bg-gradient-to-br ${gradient} overflow-auto`}
          style={{ backfaceVisibility: 'hidden' }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-primary">Question</span>
            <span className="text-xs text-text-muted">#{index + 1}</span>
          </div>
          <p className="text-sm leading-relaxed font-medium">{fc.question}</p>
          <div className="mt-3 flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-primary" />
            <span className="text-xs text-text-muted">Tap to reveal answer</span>
          </div>
        </div>

        {/* Back — Answer */}
        <div
          className={`absolute inset-0 rounded-xl border ${borderColor} p-4 sm:p-5 bg-gradient-to-br ${gradient} overflow-auto`}
          style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">Answer</span>
            <span className="text-xs text-text-muted">#{index + 1}</span>
          </div>
          <p className="text-sm leading-relaxed text-text-secondary">{fc.answer}</p>
          <div className="mt-3 flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-xs text-text-muted">Tap to see question</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function BookDetail({ book, onBack }) {
  const navigate = useNavigate()
  const [tab, setTab] = useState('reels')
  const [reels, setReels] = useState([])
  const [flashcards, setFlashcards] = useState([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(book.status)
  const isProcessing = status === 'processing'

  const fetchContent = () => {
    Promise.all([
      getFeed(1, 50, book.id).then(d => d.reels || []).catch(() => []),
      getFlashcards(book.id).catch(() => []),
    ]).then(([r, f]) => {
      setReels(r)
      setFlashcards(Array.isArray(f) ? f : f.flashcards || [])
      setLoading(false)
    })
  }

  useEffect(() => {
    setLoading(true)
    fetchContent()
  }, [book.id])

  // Real-time updates via WebSocket while processing
  useUploadWs(isProcessing ? book.id : null, {
    onReelReady: (reel) => setReels((prev) => [...prev, reel]),
    onFlashcardReady: (fc) => setFlashcards((prev) => [...prev, fc]),
    onVideoReady: (reelId, videoPath) => {
      if (videoPath) {
        setReels((prev) => prev.map((r) =>
          r.id === reelId ? { ...r, video_path: videoPath } : r
        ))
      }
    },
    onDone: (s) => setStatus(s),
  })

  const handleReelClick = (index) => {
    navigate('/', { state: { uploadId: book.id, startReelIndex: index } })
  }

  const tabs = [
    { id: 'reels', icon: Grid, label: 'Bites' },
    { id: 'flashcards', icon: Cards, label: 'Cards' },
    { id: 'chat', icon: Chat, label: 'Chat' },
  ]

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 pt-4 sm:pt-6 pb-20 md:pb-6 fade-up">
      <button onClick={onBack} className="flex items-center gap-1.5 text-text-muted hover:text-primary text-sm mb-4 cursor-pointer transition-colors">
        <ArrowL /> Back
      </button>

      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
          <File />
        </div>
        <div className="min-w-0">
          <h1 className="text-lg sm:text-xl font-bold font-display truncate">{book.filename}</h1>
          <div className="flex items-center gap-3 mt-1">
            {book.doc_type && <span className="text-xs text-text-muted">{book.doc_type}</span>}
            <span className="text-xs text-text-muted">{book.reel_count || 0} bites</span>
            <span className="text-xs text-text-muted">{book.flashcard_count || 0} cards</span>
          </div>
        </div>
      </div>

      {/* Error banner for failed uploads */}
      {book.status === 'error' && (
        <div className="bg-danger/5 border border-danger/20 rounded-xl p-4 mb-4">
          <p className="text-sm text-danger font-medium">Processing failed</p>
          <p className="text-xs text-text-muted mt-1">This document couldn't be fully processed. Try re-uploading it.</p>
          <button
            className="mt-2 text-xs text-primary font-medium hover:opacity-80 transition-opacity"
            onClick={() => navigate('/upload')}
          >
            Re-upload document
          </button>
        </div>
      )}

      {/* Summary — only show if we have content or the upload completed */}
      {(book.doc_summary || book.reel_count > 0 || book.status === 'done') && (
        <BookSummary bookId={book.id} initialSummary={book.doc_summary || null} />
      )}

      {/* Icon Tab Bar */}
      <div className="mb-4">
        <div className="flex">
          {tabs.map(t => {
            const Icon = t.icon
            const isActive = tab === t.id
            return (
              <button
                key={t.id}
                onClick={() => {
                  if (t.id === 'chat') {
                    navigate(`/chat?upload=${book.id}`)
                    return
                  }
                  setTab(t.id)
                }}
                className={`flex-1 flex items-center justify-center py-3.5 relative cursor-pointer transition-colors ${
                  isActive ? 'text-text' : 'text-text-muted hover:text-text'
                }`}
              >
                <Icon />
                {isActive && (
                  <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-10 h-0.5 bg-text rounded-full" />
                )}
              </button>
            )
          })}
        </div>
        <div className="h-px bg-border" />
      </div>

      {loading ? (
        <Spinner text="Loading content..." />
      ) : tab === 'reels' ? (
        reels.length === 0 ? (
          isProcessing ? (
            <div className="text-center py-8">
              <div className="flex justify-center gap-1.5 mb-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: `${i * 0.2}s` }} />
                ))}
              </div>
              <p className="text-sm text-text-muted">Generating bites... they'll appear here in real-time</p>
            </div>
          ) : (
            <EmptyState title="No bites yet" subtitle="Bites will appear once processing is complete" />
          )
        ) : (
          <>
            <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
              {reels.map((reel, i) => (
                <ReelThumbnail
                  key={reel.id}
                  reel={reel}
                  accent={ACCENTS[i % ACCENTS.length]}
                  onClick={() => handleReelClick(i)}
                />
              ))}
            </div>
            {isProcessing && (
              <div className="flex items-center justify-center gap-2 mt-4 py-3">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" style={{ animationDelay: `${i * 0.2}s` }} />
                  ))}
                </div>
                <span className="text-xs text-primary/80">Generating more bites...</span>
              </div>
            )}
          </>
        )
      ) : (
        flashcards.length === 0 ? (
          isProcessing ? (
            <div className="text-center py-8">
              <div className="flex justify-center gap-1.5 mb-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: `${i * 0.2}s` }} />
                ))}
              </div>
              <p className="text-sm text-text-muted">Generating flashcards...</p>
            </div>
          ) : (
            <EmptyState title="No flashcards yet" subtitle="Flashcards will appear once processing is complete" />
          )
        ) : (
          <div className="space-y-3">
            {flashcards.map((fc, i) => (
              <FlashcardItem key={fc.id} fc={fc} index={i} />
            ))}
          </div>
        )
      )}
    </div>
  )
}

export default function MyBooksPage() {
  const navigate = useNavigate()
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [selectedBook, setSelectedBook] = useState(null)
  const pollRef = useRef(null)

  const loadBooks = () => {
    setLoading(true)
    setError(false)
    getUploads()
      .then(setBooks)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  const refreshBooks = () => {
    getUploads().then(setBooks).catch(() => {})
  }

  useEffect(() => {
    loadBooks()
  }, [])

  // Poll to refresh list when any book is still processing
  useEffect(() => {
    const hasProcessing = books.some((b) => b.status === 'processing')
    if (hasProcessing) {
      pollRef.current = setInterval(refreshBooks, 5000)
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [books])

  if (selectedBook) {
    return <BookDetail book={selectedBook} onBack={() => setSelectedBook(null)} />
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <Spinner text="Loading your collections..." />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <ErrorState onRetry={loadBooks} />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 pt-8 sm:pt-10 pb-20 md:pb-6 fade-up">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold font-display mb-1">My Collections</h1>
          <p className="text-text-muted text-sm">{books.length} document{books.length !== 1 ? 's' : ''} uploaded</p>
        </div>
        <div className="hidden sm:block">
          <Button variant="secondary" onClick={() => navigate('/upload')}>
            <Upload /> Upload
          </Button>
        </div>
      </div>

      {books.length === 0 ? (
        <EmptyState
          icon={<File />}
          title="No collections yet"
          subtitle="Upload a document to get started with bites, flashcards, and chat"
        >
          <Button onClick={() => navigate('/upload')}>Upload Document</Button>
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {books.map((book) =>
            book.status === 'processing' ? (
              <ProcessingCard key={book.id} book={book} onDone={refreshBooks} onClick={() => setSelectedBook(book)} />
            ) : (
              <BookCard key={book.id} book={book} onClick={() => setSelectedBook(book)} />
            )
          )}
        </div>
      )}
    </div>
  )
}
