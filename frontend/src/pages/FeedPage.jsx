import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Swiper, SwiperSlide } from 'swiper/react'
import { Mousewheel, Keyboard } from 'swiper/modules'
import 'swiper/css'

import api, { getFeed, getAudio } from '../api'
import useStore from '../store/useStore'
import Tag from '../components/Tag'
import Button from '../components/Button'
import { Bookmark, BookmarkFill, Play, Pause, Share, Upload } from '../components/Icons'
import { Spinner, ErrorState, EmptyState } from '../components/StateScreens'

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

  const hasBg = !!reel.bgImage

  return (
    <div className="flex items-center justify-center p-4 md:p-8 h-full">
      <div className="w-full max-w-lg h-4/5 fade-up">
        <div className="bg-surface rounded-2xl p-6 md:p-8 border border-border relative overflow-hidden h-full flex flex-col">
          {hasBg && (
            <>
              <div
                className="absolute inset-0 bg-cover bg-center"
                style={{ backgroundImage: `url(${reel.bgImage})` }}
              />
              <div className="absolute inset-0 bg-black/60" />
            </>
          )}
          {!hasBg && (
            <div
              className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl"
              style={{ background: `linear-gradient(90deg, ${reel.accent}, transparent)` }}
            />
          )}

          <div className="relative z-10 flex flex-col h-full">
            <div className="flex items-center justify-between mb-4">
              <Tag color={reel.accent}>{reel.category}</Tag>
              <span className={`text-xs font-mono ${hasBg ? 'text-white/70' : 'text-text-muted'}`}>
                p. {reel.pages} &middot; {index + 1}/{total}
              </span>
            </div>

            <h2 className={`text-xl md:text-2xl font-bold font-display leading-tight mb-4 ${hasBg ? 'text-white' : ''}`}>
              {reel.title}
            </h2>

            <div className={`h-px mb-4 ${hasBg ? 'bg-white/20' : 'bg-border'}`} />

            <p className={`text-sm leading-relaxed flex-1 ${expanded ? 'overflow-y-auto' : 'line-clamp-6'} ${hasBg ? 'text-white/90' : 'text-text-secondary'}`}>
              {reel.body}
            </p>
            {!expanded && (
              <button
                onClick={() => setExpanded(true)}
                className={`text-xs font-semibold mt-2 cursor-pointer hover:underline ${hasBg ? 'text-white/80' : 'text-primary'}`}
              >
                Read more
              </button>
            )}

            <div className="flex flex-wrap gap-2 mt-4">
              {reel.keywords.map((kw) => (
                <span key={kw} className={`px-2.5 py-1 rounded-full text-xs ${hasBg ? 'bg-white/15 text-white/80' : 'bg-surface-alt text-text-secondary'}`}>
                  {kw}
                </span>
              ))}
            </div>

            <div className={`flex items-center gap-3 mt-auto pt-4 border-t ${hasBg ? 'border-white/20' : 'border-border'}`}>
              <button
                onClick={handleAudio}
                disabled={audioLoading}
                className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer ${
                  playing
                    ? (hasBg ? 'text-white' : 'text-primary')
                    : (hasBg ? 'text-white/70 hover:text-white' : 'text-text-muted hover:text-primary')
                } ${audioLoading ? 'opacity-50' : ''}`}
              >
                {playing ? <Pause /> : <Play />}
                {audioLoading ? 'Loading...' : playing ? 'Pause' : 'Listen'}
              </button>
              <button
                onClick={() => toggleBookmark(reel.id)}
                className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer ${
                  saved
                    ? 'text-accent'
                    : (hasBg ? 'text-white/70 hover:text-white' : 'text-text-muted hover:text-primary')
                }`}
              >
                {saved ? <BookmarkFill /> : <Bookmark />}
                {saved ? 'Saved' : 'Save'}
              </button>
              <button className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer ml-auto ${hasBg ? 'text-white/70 hover:text-white' : 'text-text-muted hover:text-primary'}`}>
                <Share /> Share
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function FeedPage() {
  const navigate = useNavigate()
  const { reels, setReels, appendReels, feedPage, hasMore } = useStore()
  const [initialLoading, setInitialLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  const ACCENTS = ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6']

  const mapReel = (r, i) => ({
    id: r.id,
    title: r.title,
    category: r.category || 'General',
    pages: r.page_ref || '—',
    body: r.summary || '',
    keywords: r.keywords ? r.keywords.split(',').map((k) => k.trim()).filter(Boolean) : [],
    accent: ACCENTS[i % ACCENTS.length],
    bgImage: r.bg_image ? `${api.defaults.baseURL}/${r.bg_image}` : null,
  })

  const loadReels = async () => {
    setInitialLoading(true)
    setError(false)
    try {
      const data = await getFeed(1, 10)
      if (data.reels?.length) {
        setReels(data.reels.map(mapReel))
      }
    } catch {
      setError(true)
    } finally {
      setInitialLoading(false)
    }
  }

  // Load reels from API on mount
  useEffect(() => {
    if (reels.length > 0) {
      setInitialLoading(false)
      return
    }
    loadReels()
  }, [])

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

  if (initialLoading) {
    return (
      <div className="h-[calc(100dvh-4rem)] md:h-screen">
        <Spinner text="Loading reels..." />
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-[calc(100dvh-4rem)] md:h-screen">
        <ErrorState onRetry={loadReels} />
      </div>
    )
  }

  if (reels.length === 0) {
    return (
      <div className="h-[calc(100dvh-4rem)] md:h-screen">
        <EmptyState
          icon={<Upload />}
          title="No reels yet"
          subtitle="Upload a document to get started"
        >
          <Button onClick={() => navigate('/upload')}>Upload Document</Button>
        </EmptyState>
      </div>
    )
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
        {reels.map((reel, i) => (
          <SwiperSlide key={reel.id}>
            <ReelCard reel={reel} index={i} total={reels.length} />
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
