import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getUploads, getFeed, getFlashcards } from '../api'
import Button from '../components/Button'
import Tag from '../components/Tag'
import { File, Upload, ArrowL, Cards, Chat } from '../components/Icons'
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
            <span className="font-semibold text-text">{book.reel_count || 0}</span> reels
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

function BookDetail({ book, onBack }) {
  const navigate = useNavigate()
  const [tab, setTab] = useState('reels')
  const [reels, setReels] = useState([])
  const [flashcards, setFlashcards] = useState([])
  const [loading, setLoading] = useState(true)
  const [flipped, setFlipped] = useState({})

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

  const tabs = [
    { id: 'reels', label: 'Reels', count: reels.length },
    { id: 'flashcards', label: 'Flashcards', count: flashcards.length },
  ]

  return (
    <div className="max-w-2xl mx-auto p-6 pt-6 fade-up">
      <button onClick={onBack} className="flex items-center gap-1.5 text-text-muted hover:text-primary text-sm mb-4 cursor-pointer transition-colors">
        <ArrowL /> Back to My Books
      </button>

      <div className="flex items-start gap-3 mb-6">
        <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
          <File />
        </div>
        <div>
          <h1 className="text-xl font-bold font-display">{book.filename}</h1>
          <div className="flex items-center gap-3 mt-1">
            {book.doc_type && <span className="text-xs text-text-muted">{book.doc_type}</span>}
            <span className="text-xs text-text-muted">{book.reel_count || 0} reels</span>
            <span className="text-xs text-text-muted">{book.flashcard_count || 0} flashcards</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-alt rounded-lg p-1 mb-6">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors cursor-pointer ${
              tab === t.id ? 'bg-surface text-text shadow-sm' : 'text-text-muted hover:text-text'
            }`}
          >
            {t.label} ({t.count})
          </button>
        ))}
        <button
          onClick={() => navigate(`/chat?upload=${book.id}`)}
          className="flex-1 py-2 px-3 rounded-md text-sm font-medium text-text-muted hover:text-text transition-colors cursor-pointer flex items-center justify-center gap-1.5"
        >
          <Chat /> Chat
        </button>
      </div>

      {loading ? (
        <Spinner text="Loading content..." />
      ) : tab === 'reels' ? (
        reels.length === 0 ? (
          <EmptyState title="No reels yet" subtitle="Reels will appear once processing is complete" />
        ) : (
          <div className="space-y-3">
            {reels.map((reel, i) => (
              <ReelMiniCard key={reel.id} reel={reel} accent={ACCENTS[i % ACCENTS.length]} />
            ))}
          </div>
        )
      ) : (
        flashcards.length === 0 ? (
          <EmptyState title="No flashcards yet" subtitle="Flashcards will appear once processing is complete" />
        ) : (
          <div className="space-y-3">
            {flashcards.map((fc) => (
              <div
                key={fc.id}
                onClick={() => setFlipped(prev => ({ ...prev, [fc.id]: !prev[fc.id] }))}
                className="bg-surface rounded-xl border border-border p-4 cursor-pointer hover:border-primary/30 transition-all"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Cards />
                  <span className="text-xs font-medium text-text-muted">{flipped[fc.id] ? 'Answer' : 'Question'}</span>
                </div>
                <p className="text-sm">{flipped[fc.id] ? fc.answer : fc.question}</p>
                <p className="text-xs text-primary mt-2">Tap to {flipped[fc.id] ? 'see question' : 'reveal answer'}</p>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}

function ReelMiniCard({ reel, accent }) {
  return (
    <div className="bg-surface rounded-xl border border-border p-4">
      <div className="flex items-center gap-2 mb-2">
        <Tag color={accent}>{reel.category || 'General'}</Tag>
        {reel.page_ref && <span className="text-xs text-text-muted">p. {reel.page_ref}</span>}
      </div>
      <h3 className="font-semibold text-sm mb-1">{reel.title}</h3>
      <p className="text-text-secondary text-xs line-clamp-2">{reel.summary}</p>
      {reel.keywords && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {(typeof reel.keywords === 'string' ? reel.keywords.split(',') : reel.keywords).map(kw => kw.trim()).filter(Boolean).map(kw => (
            <span key={kw} className="px-2 py-0.5 rounded-full text-xs bg-surface-alt text-text-secondary">{kw}</span>
          ))}
        </div>
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
        <Spinner text="Loading your books..." />
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
    <div className="max-w-2xl mx-auto p-6 pt-10 fade-up">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold font-display mb-1">My Books</h1>
          <p className="text-text-muted text-sm">{books.length} document{books.length !== 1 ? 's' : ''} uploaded</p>
        </div>
        <Button variant="secondary" onClick={() => navigate('/upload')}>
          <Upload /> Upload
        </Button>
      </div>

      {books.length === 0 ? (
        <EmptyState
          icon={<File />}
          title="No books yet"
          subtitle="Upload a document to get started with reels, flashcards, and chat"
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
