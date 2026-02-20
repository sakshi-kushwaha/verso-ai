import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getUploads, getFeed, getFlashcards, getDocSummary, getSummaryAudio } from '../api'
import api from '../api'
import Button from '../components/Button'
import { File, Upload, ArrowL, Cards, Chat, Volume, Pause, Play, Grid } from '../components/Icons'
import { Spinner, ErrorState, EmptyState } from '../components/StateScreens'

const ACCENTS = ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6']

function BookCard({ book, onClick }) {
  const statusColors = {
    done: 'bg-success/10 text-success',
    processing: 'bg-warning/10 text-warning',
    error: 'bg-danger/10 text-danger',
  }
  const statusLabel = book.status === 'done' ? 'Completed' : book.status === 'processing' ? 'Processing' : book.status

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

      {book.status === 'done' && (
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
        <p className="text-xs text-text-muted mt-2">Summary generation timed out. Click retry to try again.</p>
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
          minHeight: '160px',
        }}
      >
        {/* Front — Question */}
        <div
          className={`absolute inset-0 rounded-xl border ${borderColor} p-4 sm:p-5 bg-gradient-to-br ${gradient}`}
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
          className={`absolute inset-0 rounded-xl border ${borderColor} p-4 sm:p-5 bg-gradient-to-br ${gradient}`}
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

  useEffect(() => {
    setLoading(true)
    Promise.all([
      getFeed(1, 50, book.id).then(d => d.reels || []).catch(() => []),
      getFlashcards(book.id).catch(() => []),
    ]).then(([r, f]) => {
      setReels(r)
      setFlashcards(Array.isArray(f) ? f : f.flashcards || [])
      setLoading(false)
    })
  }, [book.id])

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

      {/* Summary */}
      <BookSummary bookId={book.id} initialSummary={book.doc_summary || null} />

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
          <EmptyState title="No bites yet" subtitle="Bites will appear once processing is complete" />
        ) : (
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
        )
      ) : (
        flashcards.length === 0 ? (
          <EmptyState title="No flashcards yet" subtitle="Flashcards will appear once processing is complete" />
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

  const loadBooks = () => {
    setLoading(true)
    setError(false)
    getUploads()
      .then(setBooks)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadBooks()
  }, [])

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
        <Button variant="secondary" onClick={() => navigate('/upload')}>
          <Upload /> Upload
        </Button>
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
          {books.map((book) => (
            <BookCard key={book.id} book={book} onClick={() => setSelectedBook(book)} />
          ))}
        </div>
      )}
    </div>
  )
}
