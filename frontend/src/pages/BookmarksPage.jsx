import { REELS } from '../data/mockData'
import useStore from '../store/useStore'
import Tag from '../components/Tag'
import { Bookmark, BookmarkFill } from '../components/Icons'

export default function BookmarksPage() {
  const { bookmarks, toggleBookmark } = useStore()
  const savedReels = REELS.filter((r) => bookmarks.has(r.id))

  return (
    <div className="max-w-xl mx-auto p-6 pt-10 fade-up">
      <h1 className="text-2xl font-bold font-display mb-1">Saved</h1>
      <p className="text-text-muted text-sm mb-8">Your bookmarked reels and flashcards</p>

      {savedReels.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-2xl bg-surface-alt flex items-center justify-center text-text-muted mb-4">
            <Bookmark />
          </div>
          <p className="font-semibold mb-1">No saved items yet</p>
          <p className="text-text-muted text-sm">Bookmark reels from the feed to see them here</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {savedReels.map((reel, i) => (
            <div
              key={reel.id}
              className="bg-surface rounded-xl p-5 border border-border fade-up"
              style={{
                animationDelay: `${i * 0.08}s`,
                borderLeft: `3px solid ${reel.accent}`,
              }}
            >
              <div className="flex items-start justify-between mb-2">
                <Tag color={reel.accent}>{reel.category}</Tag>
                <button
                  onClick={() => toggleBookmark(reel.id)}
                  className="text-accent hover:opacity-70 cursor-pointer"
                >
                  <BookmarkFill />
                </button>
              </div>
              <h3 className="font-semibold font-display mb-2">{reel.title}</h3>
              <p className="text-text-secondary text-sm line-clamp-2 mb-3">{reel.body}</p>
              <span className="text-text-muted text-xs font-mono">p. {reel.pages}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
