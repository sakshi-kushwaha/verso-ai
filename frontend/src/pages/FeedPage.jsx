import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Swiper, SwiperSlide } from 'swiper/react'
import { Mousewheel, Keyboard } from 'swiper/modules'
import 'swiper/css'

import { getFeed, getAudio } from '../api'
import useStore from '../store/useStore'
import Tag from '../components/Tag'
import Button from '../components/Button'
import { Bookmark, BookmarkFill, Play, Pause, Share, Upload } from '../components/Icons'

function ReelCard({ reel, index, total }) {
  const [expanded, setExpanded] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [audioLoading, setAudioLoading] = useState(false)
  const audioRef = useRef(null)
  const { bookmarks, toggleBookmark } = useStore()
  const saved = bookmarks.has(reel.id)

  const handleAudio = async () => {
    // If already playing, pause
    if (playing && audioRef.current) {
      audioRef.current.pause()
      setPlaying(false)
      return
    }

    // If audio element exists and is paused, resume
    if (audioRef.current && audioRef.current.src) {
      audioRef.current.play()
      setPlaying(true)
      return
    }

    // Fetch audio from API
    setAudioLoading(true)
    try {
      const blobUrl = await getAudio(reel.id)
      const audio = new Audio(blobUrl)
      audioRef.current = audio
      audio.onended = () => setPlaying(false)
      audio.play()
      setPlaying(true)
    } catch {
      // Audio not available — silently fail
    } finally {
      setAudioLoading(false)
    }
  }

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        if (audioRef.current.src?.startsWith('blob:')) {
          URL.revokeObjectURL(audioRef.current.src)
        }
      }
    }
  }, [])

  return (
    <div className="flex items-center justify-center p-4 md:p-8 h-full">
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
            <button
              onClick={handleAudio}
              disabled={audioLoading}
              className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer ${
                playing ? 'text-primary' : 'text-text-muted hover:text-primary'
              } ${audioLoading ? 'opacity-50' : ''}`}
            >
              {playing ? <Pause /> : <Play />}
              {audioLoading ? 'Loading...' : playing ? 'Pause' : 'Listen'}
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
  const { reels, setReels, appendReels, feedPage, hasMore } = useStore()
  const [loading, setLoading] = useState(false)

  const ACCENTS = ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6']

  const mapReel = (r, i) => ({
    id: r.id,
    title: r.title,
    category: r.category || 'General',
    pages: r.page_ref || '—',
    body: r.summary || '',
    keywords: r.keywords ? r.keywords.split(',').map((k) => k.trim()).filter(Boolean) : [],
    accent: ACCENTS[i % ACCENTS.length],
  })

  // Load reels from API on mount
  useEffect(() => {
    let cancelled = false
    async function loadReels() {
      try {
        const data = await getFeed(1, 10)
        if (!cancelled && data.reels?.length) {
          setReels(data.reels.map(mapReel))
        }
      } catch {
        // API unavailable
      }
    }
    if (reels.length === 0) loadReels()
    return () => { cancelled = true }
  }, [])

  const displayReels = reels

  // Load more when reaching end
  const handleReachEnd = async () => {
    if (!hasMore || loading) return
    setLoading(true)
    try {
      const data = await getFeed(feedPage + 1, 5)
      if (data.reels?.length) {
        appendReels(data.reels.map(mapReel))
      }
    } catch {
      // No more reels or API unavailable
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-[calc(100dvh-4rem)] md:h-screen">
      <Swiper
        direction="vertical"
        modules={[Mousewheel, Keyboard]}
        mousewheel={{ forceToAxis: true, thresholdDelta: 30, thresholdTime: 300 }}
        keyboard
        slidesPerView={1}
        speed={400}
        className="h-full"
        onReachEnd={handleReachEnd}
      >
        {displayReels.map((reel, i) => (
          <SwiperSlide key={reel.id}>
            <ReelCard reel={reel} index={i} total={displayReels.length} />
          </SwiperSlide>
        ))}

        {/* Upload CTA slide */}
        <SwiperSlide>
          <div className="flex items-center justify-center p-4 md:p-8 h-full">
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
        </SwiperSlide>
      </Swiper>
    </div>
  )
}
