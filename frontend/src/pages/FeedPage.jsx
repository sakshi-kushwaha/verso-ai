import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Swiper, SwiperSlide } from 'swiper/react'
import { Mousewheel, Keyboard } from 'swiper/modules'
import 'swiper/css'

import api, { getFeed } from '../api'
import { speak } from '../services/tts'
import useStore from '../store/useStore'
import Tag from '../components/Tag'
import Button from '../components/Button'
import { Bookmark, BookmarkFill, Play, Pause, Upload, Download, Volume, VolumeOff } from '../components/Icons'

function wrapCanvasText(ctx, text, x, y, maxW, lineH) {
  const words = text.split(' ')
  let line = ''
  for (const word of words) {
    const test = line + (line ? ' ' : '') + word
    if (ctx.measureText(test).width > maxW && line) {
      ctx.fillText(line, x, y)
      line = word
      y += lineH
    } else {
      line = test
    }
  }
  ctx.fillText(line, x, y)
  return y + lineH
}

function downloadBite(reel) {
  const safeName = reel.title.replace(/[^a-zA-Z0-9 ]/g, '').trim() || 'bite'

  if (reel.videoUrl) {
    // Video bite — backend burns text overlay via ffmpeg
    const baseURL = api.defaults.baseURL || ''
    const a = document.createElement('a')
    a.href = `${baseURL}/video/${reel.id}/download`
    a.download = `${safeName}.mp4`
    a.click()
  } else {
    // Text bite — render as PNG using Canvas
    const c = document.createElement('canvas')
    const ctx = c.getContext('2d')
    c.width = 480
    c.height = 640

    // Background
    ctx.fillStyle = '#111827'
    ctx.fillRect(0, 0, 480, 640)

    // Top accent bar
    ctx.fillStyle = reel.accent || '#3B82F6'
    ctx.fillRect(0, 0, 480, 3)

    // Category
    ctx.font = 'bold 13px sans-serif'
    ctx.fillStyle = reel.accent || '#3B82F6'
    ctx.fillText(reel.category, 28, 40)

    // Page ref
    ctx.font = '12px monospace'
    ctx.fillStyle = '#64748B'
    ctx.textAlign = 'right'
    ctx.fillText(`p. ${reel.pages}`, 452, 40)
    ctx.textAlign = 'left'

    // Title
    ctx.font = 'bold 24px sans-serif'
    ctx.fillStyle = '#F8FAFC'
    let y = wrapCanvasText(ctx, reel.title, 28, 80, 424, 30)

    // Separator
    y += 8
    ctx.strokeStyle = 'rgba(255,255,255,0.1)'
    ctx.beginPath()
    ctx.moveTo(28, y)
    ctx.lineTo(452, y)
    ctx.stroke()
    y += 16

    // Body
    ctx.font = '15px sans-serif'
    ctx.fillStyle = '#94A3B8'
    y = wrapCanvasText(ctx, reel.body, 28, y, 424, 22)

    // Keywords
    y += 16
    ctx.font = '12px sans-serif'
    ctx.fillStyle = '#64748B'
    ctx.fillText(`Keywords: ${reel.keywords.join(', ')}`, 28, y)

    c.toBlob((blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${safeName}.png`
      a.click()
      URL.revokeObjectURL(url)
    })
  }
}
import { Spinner, ErrorState, EmptyState } from '../components/StateScreens'

function VideoReelCard({ reel, index, total, isActive, onVideoError }) {
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
      <div className="relative w-full max-w-[480px] h-full bg-gray-900">

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
          onError={() => onVideoError?.(reel.id)}
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

        {/* Action buttons — bottom right */}
        <div className="absolute right-4 bottom-24 z-20 flex flex-col gap-2">
          <button onClick={() => downloadBite(reel)} className="cursor-pointer">
            <div className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center text-white">
              <Download />
            </div>
          </button>
          <button onClick={() => toggleBookmark(reel.id)} className="cursor-pointer">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              saved ? 'bg-accent/20 text-accent' : 'bg-black/40 backdrop-blur-sm text-white'
            }`}>
              {saved ? <BookmarkFill /> : <Bookmark />}
            </div>
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

function ReelCard({ reel, index, total }) {
  const [expanded, setExpanded] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [audioLoading, setAudioLoading] = useState(false)
  const ttsRef = useRef(null)
  const { bookmarks, toggleBookmark } = useStore()
  const saved = bookmarks.has(reel.id)

  const handleAudio = async () => {
    // Block rapid clicks while loading
    if (audioLoading) return

    // If already playing, pause
    if (playing && ttsRef.current) {
      ttsRef.current.pause()
      setPlaying(false)
      return
    }

    // If paused with existing controller, resume
    if (ttsRef.current && !playing) {
      ttsRef.current.resume()
      setPlaying(true)
      return
    }

    // Start new playback — server TTS (Piper) first, browser fallback
    setAudioLoading(true)
    try {
      // Cancel any lingering previous audio
      if (ttsRef.current) { ttsRef.current.cancel(); ttsRef.current = null }
      const controller = await speak(reel.id, reel.narration, () => {
        setPlaying(false)
        ttsRef.current = null
      })
      ttsRef.current = controller
      setPlaying(true)
    } catch {
      // Audio not available — silently fail
      ttsRef.current = null
    } finally {
      setAudioLoading(false)
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (ttsRef.current) ttsRef.current.cancel()
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
                onClick={() => downloadBite(reel)}
                className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer ${
                  hasBg ? 'text-white/70 hover:text-white' : 'text-text-muted hover:text-primary'
                }`}
              >
                <Download />
                Download
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
            </div>
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
  const { reels, setReels, appendReels, feedPage, hasMore } = useStore()
  const [initialLoading, setInitialLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [tab, setTab] = useState('all')
  const [failedVideos, setFailedVideos] = useState(new Set())
  const [initialSlide, setInitialSlide] = useState(0)
  const bookNavState = useRef(location.state)

  const ACCENTS = ['#3B82F6', '#06B6D4', '#F472B6', '#F59E0B', '#10B981', '#8B5CF6']

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

  if (reels.length === 0) {
    return (
      <div className="h-[calc(100dvh-4rem)] md:h-screen flex flex-col">
        {tabBar}
        <div className="flex-1">
          <EmptyState
            icon={<Upload />}
            title="No bites yet"
            subtitle={tab === 'my-docs' ? 'Upload a document to see your bites here' : 'Upload a document to get started'}
          >
            <Button onClick={() => navigate('/upload')}>Upload Document</Button>
          </EmptyState>
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
          swiper.allowSlideNext = swiper.activeIndex < reels.length - 1
        }}
      >
        {reels.map((reel, i) => (
          <SwiperSlide key={reel.id}>
            {reel.videoUrl && !failedVideos.has(reel.id) ? (
              <VideoReelCard reel={reel} index={i} total={reels.length} isActive={i === activeIndex} onVideoError={(id) => setFailedVideos(prev => new Set(prev).add(id))} />
            ) : (
              <ReelCard reel={reel} index={i} total={reels.length} />
            )}
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
