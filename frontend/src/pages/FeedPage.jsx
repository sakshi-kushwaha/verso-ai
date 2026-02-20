import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Swiper, SwiperSlide } from 'swiper/react'
import { Mousewheel, Keyboard } from 'swiper/modules'
import 'swiper/css'

import api, { getFeed } from '../api'
import useStore from '../store/useStore'
import Tag from '../components/Tag'
import Button from '../components/Button'
import { Bookmark, BookmarkFill, Play, Pause, Upload, Volume, VolumeOff } from '../components/Icons'
import { Spinner, ErrorState, EmptyState } from '../components/StateScreens'

function VideoReelCard({ reel, index, total, isActive }) {
  const videoRef = useRef(null)
  const [paused, setPaused] = useState(false)
  const [buffering, setBuffering] = useState(true)
  const { bookmarks, toggleBookmark } = useStore()
  const saved = bookmarks.has(reel.id)
  const [progress, setProgress] = useState(0)
  const [muted, setMuted] = useState(false)

  // Autoplay when active slide, pause when not
  useEffect(() => {
    if (!videoRef.current) return
    if (isActive) {
      videoRef.current.currentTime = 0
      videoRef.current.muted = false
      setProgress(0)
      setPaused(false)
      setMuted(false)
      videoRef.current.play().catch(() => {})
    } else {
      videoRef.current.pause()
    }
  }, [isActive])

  const togglePlay = useCallback(() => {
    if (!videoRef.current) return
    if (videoRef.current.paused) {
      videoRef.current.play().catch(() => {})
      setPaused(false)
    } else {
      videoRef.current.pause()
      setPaused(true)
    }
  }, [])

  const toggleMute = useCallback(() => {
    if (!videoRef.current) return
    videoRef.current.muted = !videoRef.current.muted
    setMuted(videoRef.current.muted)
  }, [])

  const handleSeek = useCallback((e) => {
    if (!videoRef.current || !videoRef.current.duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    videoRef.current.currentTime = ratio * videoRef.current.duration
  }, [])

  return (
    <div className="flex items-center justify-center h-full bg-black">
      <div className="relative w-full max-w-[480px] md:max-w-[640px] lg:max-w-[768px] h-full bg-gray-900">

        {/* Full-screen video */}
        <video
          ref={videoRef}
          src={reel.videoUrl}
          className="absolute inset-0 w-full h-full object-cover"
          loop
          playsInline
          preload="metadata"
          onClick={togglePlay}
          onWaiting={() => setBuffering(true)}
          onCanPlay={() => setBuffering(false)}
          onPlaying={() => setBuffering(false)}
          onTimeUpdate={(e) => {
            const v = e.target
            if (v.duration) setProgress((v.currentTime / v.duration) * 100)
          }}
          onError={() => {}}
        />

        {/* Buffering indicator */}
        {buffering && isActive && !paused && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <div className="flex gap-1.5">
              <span className="w-2 h-2 bg-white/80 rounded-full animate-pulse" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-white/80 rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-white/80 rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}

        {/* Tap-to-pause overlay */}
        {paused && (
          <div
            className="absolute inset-0 flex items-center justify-center bg-black/20 z-10 cursor-pointer"
            onClick={togglePlay}
          >
            <div className="w-16 h-16 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center">
              <Play />
            </div>
          </div>
        )}

        {/* Mute button — top right */}
        <button onClick={toggleMute} className="absolute top-4 right-4 z-20 cursor-pointer">
          <div className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center text-white">
            {muted ? <VolumeOff /> : <Volume />}
          </div>
        </button>

        {/* Save button — bottom right, aligned vertically with mute */}
        <div className="absolute right-3 bottom-20 z-20">
          <button
            onClick={() => toggleBookmark(reel.id)}
            className="flex flex-col items-center gap-1 cursor-pointer"
          >
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              saved ? 'bg-accent/20' : 'bg-black/40 backdrop-blur-sm'
            }`}>
              {saved ? <BookmarkFill /> : <Bookmark />}
            </div>
            <span className="text-white text-[10px]">{saved ? 'Saved' : 'Save'}</span>
          </button>
        </div>

        {/* Bottom info — minimal, over video */}
        <div className="absolute bottom-0 left-0 right-0 z-10 p-4 pb-6 bg-gradient-to-t from-black/70 via-black/30 to-transparent">
          <Tag color={reel.accent}>{reel.category}</Tag>
          <h2 className="text-white font-bold font-display text-base leading-snug mt-2">
            {reel.title}
          </h2>
          <p className="text-white/70 text-xs line-clamp-2 mt-1">
            {reel.body}
          </p>
        </div>

        {/* Progress bar at very bottom */}
        <div
          className="absolute bottom-0 left-0 right-0 z-20 h-3 flex items-end cursor-pointer"
          onClick={handleSeek}
        >
          <div className="w-full h-1 bg-white/20">
            <div className="h-full bg-primary rounded-full" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>
    </div>
  )
}

const TABS = [
  { id: 'all', label: 'All' },
  { id: 'explore', label: 'Explore' },
  { id: 'my-docs', label: 'My Docs' },
]

export default function FeedPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { reels, setReels, appendReels, feedPage, hasMore, feedStale, bgUpload } = useStore()
  const [initialLoading, setInitialLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [tab, setTab] = useState('all')
  const [initialSlide, setInitialSlide] = useState(0)
  const bookNavState = useRef(location.state)

  const ACCENTS = ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6']

  const mapReel = (r, i) => ({
    id: r.id,
    title: r.title,
    category: r.category || 'General',
    pages: r.page_ref || '—',
    body: r.summary || '',
    narration: r.narration || r.summary || '',
    keywords: r.keywords ? r.keywords.split(',').map((k) => k.trim()).filter(Boolean) : [],
    accent: ACCENTS[i % ACCENTS.length],
    bgImage: r.bg_image ? `${api.defaults.baseURL}/${r.bg_image}` : null,
    videoUrl: r.video_path ? `${api.defaults.baseURL}/video/${r.id}` : null,
  })

  const loadReels = async (activeTab = tab) => {
    setInitialLoading(true)
    setError(false)
    try {
      const data = await getFeed(1, 10, null, activeTab)
      if (data.reels?.length) {
        setReels(data.reels.map(mapReel))
      } else {
        setReels([])
      }
    } catch {
      setError(true)
    } finally {
      setInitialLoading(false)
    }
  }

  const handleTabChange = (newTab) => {
    if (newTab === tab) return
    setTab(newTab)
    setReels([])
    setActiveIndex(0)
    loadReels(newTab)
  }

  // Load reels from API on mount — or from a specific book if navigated from BookDetail
  useEffect(() => {
    const nav = bookNavState.current
    if (nav?.uploadId) {
      // Clear the state so refresh doesn't re-trigger
      window.history.replaceState({}, '')
      bookNavState.current = null
      setInitialLoading(true)
      setTab('my-docs')
      getFeed(1, 50, nav.uploadId)
        .then(data => {
          if (data.reels?.length) {
            setReels(data.reels.map(mapReel))
            const idx = nav.startReelIndex || 0
            setInitialSlide(idx)
            setActiveIndex(idx)
          } else {
            setReels([])
          }
        })
        .catch(() => setError(true))
        .finally(() => setInitialLoading(false))
      return
    }
    if (reels.length > 0) {
      setInitialLoading(false)
      return
    }
    loadReels()
  }, [])

  // Reload feed when processing finishes and bgUpload is cleared
  useEffect(() => {
    if (feedStale) loadReels()
  }, [feedStale])

  // Load more when reaching end
  const handleReachEnd = async () => {
    if (!hasMore || loading) return
    setLoading(true)
    try {
      const data = await getFeed(feedPage + 1, 5, null, tab)
      if (data.reels?.length) {
        appendReels(data.reels.map(mapReel))
      }
    } catch {
      // No more reels or API unavailable
    } finally {
      setLoading(false)
    }
  }

  const tabBar = (
    <div className="flex items-center gap-2 px-4 py-2 bg-surface border-b border-border">
      {TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => handleTabChange(t.id)}
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors cursor-pointer ${
            tab === t.id
              ? 'bg-primary text-white'
              : 'bg-surface-alt text-text-secondary hover:text-text-primary'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )

  if (initialLoading) {
    return (
      <div className="h-[calc(100dvh-4rem)] md:h-screen flex flex-col">
        {tabBar}
        <div className="flex-1">
          <Spinner text="Loading bites..." />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-[calc(100dvh-4rem)] md:h-screen flex flex-col">
        {tabBar}
        <div className="flex-1">
          <ErrorState onRetry={() => loadReels()} />
        </div>
      </div>
    )
  }

  const videoReels = reels.filter((r) => r.videoUrl)
  const isGenerating = bgUpload && bgUpload.status !== 'done' && bgUpload.status !== 'error'

  if (videoReels.length === 0) {
    return (
      <div className="h-[calc(100dvh-4rem)] md:h-screen flex flex-col">
        {tabBar}
        <div className="flex-1">
          {isGenerating ? (
            <Spinner text="Generating your bites..." />
          ) : (
            <EmptyState
              icon={<Upload />}
              title="No bites yet"
              subtitle={tab === 'my-docs' ? 'Upload a document to see your bites here' : 'Upload a document to get started'}
            >
              <Button onClick={() => navigate('/upload')}>Upload Document</Button>
            </EmptyState>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="h-[calc(100dvh-4rem)] md:h-screen flex flex-col">
      {tabBar}
      <Swiper
        direction="vertical"
        modules={[Mousewheel, Keyboard]}
        mousewheel={{ forceToAxis: true, thresholdDelta: 30, thresholdTime: 300 }}
        keyboard
        slidesPerView={1}
        speed={400}
        initialSlide={initialSlide}
        className="h-full flex-1"
        onReachEnd={handleReachEnd}
        onSlideChange={(swiper) => {
          setActiveIndex(swiper.activeIndex)
          swiper.allowSlideNext = swiper.activeIndex < videoReels.length - 1
        }}
      >
        {videoReels.map((reel, i) => (
          <SwiperSlide key={reel.id}>
            <VideoReelCard reel={reel} index={i} total={videoReels.length} isActive={i === activeIndex} />
          </SwiperSlide>
        ))}

        {/* Swiper needs this slide to initialize — scroll guard prevents reaching it */}
        <SwiperSlide>
          <div className="flex items-center justify-center p-4 md:p-8 h-full">
            <div className="flex flex-col items-center text-center gap-4 fade-up">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-2">
                <Upload />
              </div>
              <h2 className="text-xl md:text-2xl font-bold font-display">Upload a new document</h2>
              <p className="text-text-secondary text-sm max-w-xs">
                Turn any PDF or article into bite-sized bites, flashcards, and more.
              </p>
              <Button onClick={() => navigate('/upload')}>Upload Document</Button>
            </div>
          </div>
        </SwiperSlide>
      </Swiper>
    </div>
  )
}
