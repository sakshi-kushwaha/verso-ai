import { useEffect, useState } from 'react'
import useStore from '../store/useStore'
import Tag from '../components/Tag'
import { Bookmark, BookmarkFill, Cards } from '../components/Icons'
import { Spinner, EmptyState } from '../components/StateScreens'

const ACCENTS = ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6']

export default function BookmarksPage() {
  const { bookmarkItems, loadBookmarks, toggleBookmark } = useStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadBookmarks().finally(() => setLoading(false))
  }, [])

  const reelBookmarks = bookmarkItems.filter((b) => b.reel_id && b.reel_title)
  const fcBookmarks = bookmarkItems.filter((b) => b.flashcard_id && b.fc_question)

  if (loading) {
    return (
      <div className="max-w-xl mx-auto p-6 pt-10">
        <Spinner text="Loading saved items..." />
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto p-6 pt-10 fade-up">
      <h1 className="text-2xl font-bold font-display mb-1">Saved</h1>
      <p className="text-text-muted text-sm mb-8">Your bookmarked reels and flashcards</p>

      {reelBookmarks.length === 0 && fcBookmarks.length === 0 ? (
        <EmptyState
          icon={<Bookmark />}
          title="No saved items yet"
          subtitle="Bookmark reels from the feed to see them here"
        />
      ) : (
        <div className="flex flex-col gap-4">
          {reelBookmarks.map((b, i) => (
            <div
              key={b.id}
              className="bg-surface rounded-xl p-5 border border-border fade-up"
              style={{
                animationDelay: `${i * 0.08}s`,
                borderLeft: `3px solid ${ACCENTS[i % ACCENTS.length]}`,
              }}
            >
              <div className="flex items-start justify-between mb-2">
                <Tag color={ACCENTS[i % ACCENTS.length]}>{b.reel_category || 'General'}</Tag>
                <button
                  onClick={() => toggleBookmark(b.reel_id)}
                  className="text-accent hover:opacity-70 cursor-pointer"
                >
                  <BookmarkFill />
                </button>
              </div>
              <h3 className="font-semibold font-display mb-2">{b.reel_title}</h3>
              <p className="text-text-secondary text-sm line-clamp-2 mb-3">{b.reel_summary}</p>
              {b.reel_page_ref && (
                <span className="text-text-muted text-xs font-mono">p. {b.reel_page_ref}</span>
              )}
            </div>
          ))}

          {fcBookmarks.length > 0 && (
            <>
              {reelBookmarks.length > 0 && (
                <h2 className="text-sm font-semibold text-text-muted mt-4">Flashcards</h2>
              )}
              {fcBookmarks.map((b, i) => (
                <div
                  key={b.id}
                  className="bg-surface rounded-xl p-5 border border-border fade-up"
                  style={{ animationDelay: `${(reelBookmarks.length + i) * 0.08}s` }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Cards />
                    <span className="text-xs font-medium text-text-muted">Flashcard</span>
                  </div>
                  <p className="text-sm font-medium mb-1">{b.fc_question}</p>
                  <p className="text-text-secondary text-xs">{b.fc_answer}</p>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
