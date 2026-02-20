import { useState, useEffect } from 'react'
import { getFlashcards } from '../api'
import Button from '../components/Button'
import Tag from '../components/Tag'
import { ArrowL, ArrowR, Flip } from '../components/Icons'
import { Spinner, ErrorState, EmptyState } from '../components/StateScreens'

export default function FlashcardsPage() {
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  const loadCards = async () => {
    setLoading(true)
    setError(false)
    try {
      const data = await getFlashcards()
      setCards(data)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCards()
  }, [])

  if (loading) return <Spinner text="Loading flashcards..." />
  if (error) return <ErrorState onRetry={loadCards} />
  if (cards.length === 0) {
    return (
      <EmptyState
        icon={<Flip />}
        title="No flashcards yet"
        subtitle="Upload a document to generate flashcards"
      />
    )
  }

  const card = cards[index]
  const flip = () => setFlipped(!flipped)
  const prev = () => { setIndex(Math.max(0, index - 1)); setFlipped(false) }
  const next = () => { setIndex(Math.min(cards.length - 1, index + 1)); setFlipped(false) }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-6 fade-up">
      {/* Counter */}
      <p className="text-text-muted text-sm font-mono mb-6">
        {index + 1} / {cards.length}
      </p>

      {/* Flip card */}
      <div
        className="w-full max-w-md cursor-pointer mb-8"
        style={{ perspective: '1000px' }}
        onClick={flip}
      >
        <div
          className="relative w-full transition-transform duration-500"
          style={{
            transformStyle: 'preserve-3d',
            transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
            minHeight: '280px',
          }}
        >
          {/* Front */}
          <div
            className="absolute inset-0 rounded-2xl bg-surface border border-border p-8 flex flex-col items-center justify-center text-center"
            style={{ backfaceVisibility: 'hidden' }}
          >
            <Tag className="mb-4">Question</Tag>
            <p className="text-lg font-semibold font-display leading-snug mb-6">
              {card.question}
            </p>
            <span className="text-text-muted text-xs font-bold uppercase tracking-widest">
              Tap to reveal
            </span>
          </div>

          {/* Back */}
          <div
            className="absolute inset-0 rounded-2xl p-8 flex flex-col items-center justify-center text-center"
            style={{
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)',
              background: 'linear-gradient(135deg, #1E293B, #111827)',
              border: '1px solid rgba(59,130,246,0.15)',
            }}
          >
            <Tag color="#10B981" className="mb-4">Answer</Tag>
            <p className="text-sm text-text-secondary leading-relaxed">
              {card.answer}
            </p>
          </div>
        </div>
      </div>

      {/* Confidence buttons (when flipped) */}
      {flipped && (
        <div className="flex gap-3 mb-6 scale-in">
          <Button variant="error" onClick={next} className="px-5 py-2 text-xs">
            Missed
          </Button>
          <Button variant="warning" onClick={next} className="px-5 py-2 text-xs">
            Review
          </Button>
          <Button variant="success" onClick={next} className="px-5 py-2 text-xs">
            Got it
          </Button>
        </div>
      )}

      {/* Navigation (when not flipped) */}
      {!flipped && (
        <div className="flex items-center gap-4">
          <Button variant="secondary" onClick={prev} disabled={index === 0} className="px-4">
            <ArrowL />
          </Button>
          <Button variant="secondary" onClick={flip} className="px-4">
            <Flip />
          </Button>
          <Button variant="secondary" onClick={next} disabled={index === cards.length - 1} className="px-4">
            <ArrowR />
          </Button>
        </div>
      )}

      {/* Dot indicators */}
      <div className="flex gap-2 mt-8">
        {cards.map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-all ${
              i === index ? 'bg-primary w-6' : 'bg-surface-alt'
            }`}
          />
        ))}
      </div>
    </div>
  )
}
