import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { REELS } from '../data/mockData'
import useStore from '../store/useStore'
import Tag from '../components/Tag'
import Button from '../components/Button'
import { Bookmark, BookmarkFill, Play, Share, ChevDown, Upload } from '../components/Icons'

const snapH = 'h-[calc(100dvh-4rem)] md:h-screen snap-start'

function ReelCard({ reel, index, total }) {
  const [expanded, setExpanded] = useState(false)
  const { bookmarks, toggleBookmark } = useStore()
  const saved = bookmarks.has(reel.id)

  return (
    <div className={`${snapH} flex items-center justify-center p-4 md:p-8`}>
      <div className="w-full max-w-lg h-4/5 fade-up">
        <div className="bg-surface rounded-2xl p-6 md:p-8 border border-border relative overflow-hidden h-full flex flex-col">
          <div
            className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl"
            style={{ background: `linear-gradient(90deg, ${reel.accent}, transparent)` }}
          />

          <div className="flex items-center justify-between mb-4">
            <Tag color={reel.accent}>{reel.category}</Tag>
            <span className="text-text-muted text-xs font-mono">
              p. {reel.pages} &middot; {index + 1}/{total}
            </span>
          </div>

          <h2 className="text-xl md:text-2xl font-bold font-display leading-tight mb-4">
            {reel.title}
          </h2>

          <div className="h-px bg-border mb-4" />

          <p className={`text-text-secondary text-sm leading-relaxed flex-1 ${expanded ? 'overflow-y-auto' : 'line-clamp-6'}`}>
            {reel.body}
          </p>
          {!expanded && (
            <button
              onClick={() => setExpanded(true)}
              className="text-primary text-xs font-semibold mt-2 cursor-pointer hover:underline"
            >
              Read more
            </button>
          )}

          <div className="flex flex-wrap gap-2 mt-4">
            {reel.keywords.map((kw) => (
              <span key={kw} className="px-2.5 py-1 rounded-full text-xs bg-surface-alt text-text-secondary">
                {kw}
              </span>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-auto pt-4 border-t border-border">
            <button className="flex items-center gap-1.5 text-text-muted hover:text-primary text-sm transition-colors cursor-pointer">
              <Play /> Listen
            </button>
            <button
              onClick={() => toggleBookmark(reel.id)}
              className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer ${
                saved ? 'text-accent' : 'text-text-muted hover:text-primary'
              }`}
            >
              {saved ? <BookmarkFill /> : <Bookmark />}
              {saved ? 'Saved' : 'Save'}
            </button>
            <button className="flex items-center gap-1.5 text-text-muted hover:text-primary text-sm transition-colors cursor-pointer ml-auto">
              <Share /> Share
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function FeedPage() {
  const navigate = useNavigate()
  return (
    <div className="h-[calc(100dvh-4rem)] md:h-screen overflow-y-auto snap-y snap-mandatory">
      {REELS.map((reel, i) => (
        <ReelCard key={reel.id} reel={reel} index={i} total={REELS.length} />
      ))}

      <div className={`${snapH} flex items-center justify-center p-4 md:p-8`}>
        <div className="flex flex-col items-center text-center gap-4 fade-up">
          <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-2">
            <Upload />
          </div>
          <h2 className="text-xl md:text-2xl font-bold font-display">Upload a new document</h2>
          <p className="text-text-secondary text-sm max-w-xs">
            Turn any PDF or article into bite-sized reels, flashcards, and more.
          </p>
          <Button onClick={() => navigate('/upload')}>Upload Document</Button>
        </div>
      </div>

      <div className="fixed bottom-24 md:bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center text-text-muted float-anim pointer-events-none">
        <span className="text-[10px] font-bold uppercase tracking-widest mb-1">Swipe Up</span>
        <ChevDown />
      </div>
    </div>
  )
}
