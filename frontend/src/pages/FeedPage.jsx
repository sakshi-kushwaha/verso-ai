import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Swiper, SwiperSlide } from 'swiper/react'
import { Mousewheel, Keyboard } from 'swiper/modules'
import 'swiper/css'

import api, { getFeed } from '../api'
import { mapReel } from '../utils/reelMapper'
import { speak } from '../services/tts'
import useStore from '../store/useStore'
import Button from '../components/Button'
import { Bookmark, BookmarkFill, Heart, HeartFill, Play, Pause, Upload, Download, Volume, VolumeOff } from '../components/Icons'
import useReelTracker from '../hooks/useReelTracker'

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

async function downloadBite(reel, isGradient = false, onProgress = null) {
  const safeName = reel.title.replace(/[^a-zA-Z0-9 ]/g, '').trim() || 'bite'

  if (reel.videoUrl && !isGradient) {
    // Video bite — fetch with progress tracking
    const baseURL = api.defaults.baseURL || ''
    const res = await fetch(`${baseURL}/video/${reel.id}/download`)
    if (!res.ok) throw new Error('Download failed')
    const contentLength = res.headers.get('content-length')
    const total = contentLength ? parseInt(contentLength, 10) : 0

    if (total && onProgress && res.body) {
      const reader = res.body.getReader()
      const chunks = []
      let received = 0
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        chunks.push(value)
        received += value.length
        onProgress(Math.min(99, Math.round((received / total) * 100)))
      }
      const blob = new Blob(chunks)
      onProgress(100)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${safeName}.mp4`
      a.click()
      URL.revokeObjectURL(url)
    } else {
      const blob = await res.blob()
      onProgress?.(100)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${safeName}.mp4`
      a.click()
      URL.revokeObjectURL(url)
    }
  } else {
    // Text bite — render as PNG matching the feed card appearance
    const c = document.createElement('canvas')
    const ctx = c.getContext('2d')
    c.width = 1080
    c.height = 1920
    const W = c.width, H = c.height
    const margin = 60

    // Load the same background image used in the feed card
    // Fetch as blob to avoid CORS issues with canvas tainting
    const baseURL = api.defaults.baseURL || ''
    const bgUrl = reel.bgImage
      || `${baseURL}/bg-images/general/${String((reel.id % 10) + 1).padStart(2, '0')}.jpg`

    let bgLoaded = false
    try {
      const resp = await fetch(bgUrl)
      const blob = await resp.blob()
      const bmpUrl = URL.createObjectURL(blob)
      const img = new window.Image()
      img.src = bmpUrl
      await new Promise((resolve, reject) => {
        img.onload = resolve
        img.onerror = reject
        setTimeout(reject, 5000)
      })
      // Draw background (cover)
      const scale = Math.max(W / img.width, H / img.height)
      const iw = img.width * scale, ih = img.height * scale
      ctx.drawImage(img, (W - iw) / 2, (H - ih) / 2, iw, ih)
      URL.revokeObjectURL(bmpUrl)
      bgLoaded = true
    } catch {
      // Fallback: solid dark background
      ctx.fillStyle = '#0A0F1A'
      ctx.fillRect(0, 0, W, H)
    }

    // Dark gradient overlay (matches GradientPostCard CSS)
    const grad = ctx.createLinearGradient(0, 0, 0, H)
    grad.addColorStop(0, 'rgba(0,0,0,0.6)')
    grad.addColorStop(0.5, 'rgba(0,0,0,0.4)')
    grad.addColorStop(1, 'rgba(0,0,0,0.8)')
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, W, H)

    // Title
    ctx.font = 'bold 52px sans-serif'
    ctx.fillStyle = '#FFFFFF'
    let y = wrapCanvasText(ctx, reel.title, margin, 160, W - margin * 2, 64)

    // Short separator (matches GradientPostCard)
    y += 20
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(margin, y)
    ctx.lineTo(margin + 160, y)
    ctx.stroke()
    y += 32

    // Body
    ctx.font = '32px sans-serif'
    ctx.fillStyle = 'rgba(255,255,255,0.75)'
    y = wrapCanvasText(ctx, reel.body, margin, y, W - margin * 2, 44)

    // Keywords as hashtags
    y += 40
    ctx.font = '26px sans-serif'
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    const kwText = reel.keywords.map((kw) => '#' + kw.replace(/\s+/g, '')).join('  ')
    ctx.fillText(kwText, margin, y)

    onProgress?.(100)
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

/* ── Circular progress ring for download button ── */
function DownloadProgressRing({ progress, size = 40, stroke = 3 }) {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const offset = circ - (progress / 100) * circ
  return (
    <svg width={size} height={size} className="absolute inset-0 -rotate-90 pointer-events-none">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#00e5ff" strokeWidth={stroke}
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        className="transition-[stroke-dashoffset] duration-200" />
    </svg>
  )
}

/* ── Download toast notifications ── */
function DownloadToast({ message, type }) {
  if (!message) return null
  return (
    <div className={`fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg backdrop-blur-sm fade-up ${
      type === 'success' ? 'bg-emerald-500/90 text-white' : type === 'error' ? 'bg-red-500/90 text-white' : 'bg-white/15 text-white'
    }`}>
      {message}
    </div>
  )
}

/* ── Shared download hook ── */
function useDownload() {
  const [downloading, setDownloading] = useState(false)
  const [dlProgress, setDlProgress] = useState(0)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  const showToast = (message, type = 'info') => {
    clearTimeout(toastTimer.current)
    setToast({ message, type })
    toastTimer.current = setTimeout(() => setToast(null), 2500)
  }

  const startDownload = async (reel, isGradient = false) => {
    if (downloading) return
    setDownloading(true)
    setDlProgress(0)
    showToast('Downloading...')
    try {
      await downloadBite(reel, isGradient, (p) => setDlProgress(p))
      showToast('Download complete!', 'success')
    } catch {
      showToast('Download failed', 'error')
    } finally {
      setTimeout(() => { setDownloading(false); setDlProgress(0) }, 600)
    }
  }

  useEffect(() => { return () => clearTimeout(toastTimer.current) }, [])

  return { downloading, dlProgress, toast, startDownload }
}

function VideoReelCard({ reel, index, total, isActive, onVideoError }) {
  const videoRef = useRef(null)
  const [paused, setPaused] = useState(false)
  const [buffering, setBuffering] = useState(true)
  const { bookmarks, toggleBookmark, likes, toggleLike, muted, toggleMuted } = useStore()
  const saved = bookmarks.has(reel.id)
  const liked = likes.has(reel.id)
  const [progress, setProgress] = useState(0)
  const { downloading, dlProgress, toast, startDownload } = useDownload()
  const seekingRef = useRef(false)
  const progressBarRef = useRef(null)

  // Autoplay when active slide, pause when not
  useEffect(() => {
    if (!videoRef.current) return
    if (isActive) {
      videoRef.current.currentTime = 0
      videoRef.current.muted = muted
      setProgress(0)
      setPaused(false)
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

  // Sync video element muted state when global mute changes
  useEffect(() => {
    if (videoRef.current) videoRef.current.muted = muted
  }, [muted])

  const toggleMute = useCallback(() => {
    toggleMuted()
  }, [toggleMuted])

  const seekToX = useCallback((clientX) => {
    if (!videoRef.current || !videoRef.current.duration || !isFinite(videoRef.current.duration)) return
    if (!progressBarRef.current) return
    const rect = progressBarRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    videoRef.current.currentTime = ratio * videoRef.current.duration
    setProgress(ratio * 100)
  }, [])

  const handleSeek = useCallback((e) => seekToX(e.clientX), [seekToX])

  // Native non-passive touch listeners — React's synthetic events are passive
  // and can't preventDefault, so Swiper steals the gesture. Attach directly.
  useEffect(() => {
    const el = progressBarRef.current
    if (!el) return
    const onStart = (e) => {
      e.preventDefault()
      e.stopPropagation()
      seekingRef.current = true
      seekToX(e.touches[0].clientX)
    }
    const onMove = (e) => {
      if (!seekingRef.current) return
      e.preventDefault()
      e.stopPropagation()
      seekToX(e.touches[0].clientX)
    }
    const onEnd = (e) => {
      if (!seekingRef.current) return
      e.stopPropagation()
      seekingRef.current = false
    }
    el.addEventListener('touchstart', onStart, { passive: false })
    el.addEventListener('touchmove', onMove, { passive: false })
    el.addEventListener('touchend', onEnd)
    return () => {
      el.removeEventListener('touchstart', onStart)
      el.removeEventListener('touchmove', onMove)
      el.removeEventListener('touchend', onEnd)
    }
  }, [seekToX])

  return (
    <div className="flex items-center justify-center h-full bg-black">
      <DownloadToast {...toast} />
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
          onLoadedMetadata={() => setBuffering(false)}
          onTimeUpdate={(e) => {
            if (seekingRef.current) return
            const v = e.target
            if (v.duration && isFinite(v.duration)) setProgress((v.currentTime / v.duration) * 100)
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
          <button onClick={() => toggleLike(reel.id)} className="cursor-pointer">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              liked ? 'bg-red-500/20 text-red-500' : 'bg-black/40 backdrop-blur-sm text-white'
            }`}>
              {liked ? <HeartFill /> : <Heart />}
            </div>
          </button>
          <button onClick={() => startDownload(reel)} disabled={downloading} className="cursor-pointer relative">
            <div className={`w-10 h-10 rounded-full backdrop-blur-sm flex items-center justify-center text-white ${downloading ? 'bg-primary/30' : 'bg-black/40'}`}>
              {downloading ? (
                <span className="text-[10px] font-bold tabular-nums">{dlProgress}%</span>
              ) : (
                <Download />
              )}
            </div>
            {downloading && <DownloadProgressRing progress={dlProgress} />}
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
          <h2 className="text-white font-bold font-display text-base leading-snug">
            {reel.title}
          </h2>
          <p className="text-white/60 text-xs mt-1">{reel.oneLiner}</p>
        </div>

        {/* Progress bar at very bottom — draggable on touch */}
        <div
          ref={progressBarRef}
          className="absolute bottom-0 left-0 right-0 z-20 h-6 flex items-end cursor-pointer"
          style={{ touchAction: 'none' }}
          onClick={handleSeek}
        >
          <div className="w-full h-[3px] bg-white/20">
            <div className="h-full bg-white rounded-full" style={{ width: `${progress}%` }} />
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
  const { bookmarks, toggleBookmark, likes, toggleLike } = useStore()
  const saved = bookmarks.has(reel.id)
  const { downloading, dlProgress, toast, startDownload } = useDownload()
  const liked = likes.has(reel.id)

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
      <DownloadToast {...toast} />
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
            <div className="flex items-center justify-end mb-4">
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
                onClick={() => startDownload(reel)}
                disabled={downloading}
                className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer relative ${
                  downloading
                    ? (hasBg ? 'text-primary' : 'text-primary')
                    : (hasBg ? 'text-white/70 hover:text-white' : 'text-text-muted hover:text-primary')
                } ${downloading ? 'opacity-80' : ''}`}
              >
                <span className="relative inline-flex items-center justify-center w-[18px] h-[18px]">
                  <Download />
                  {downloading && <DownloadProgressRing progress={dlProgress} size={18} stroke={2} />}
                </span>
                {downloading ? `${dlProgress}%` : 'Download'}
              </button>
              <button
                onClick={() => toggleLike(reel.id)}
                className={`flex items-center gap-1.5 text-sm transition-colors cursor-pointer ${
                  liked
                    ? 'text-red-500'
                    : (hasBg ? 'text-white/70 hover:text-white' : 'text-text-muted hover:text-primary')
                }`}
              >
                {liked ? <HeartFill /> : <Heart />}
                {liked ? 'Liked' : 'Like'}
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

function GradientPostCard({ reel, index, total, isActive }) {
  const { bookmarks, toggleBookmark, likes, toggleLike } = useStore()
  const saved = bookmarks.has(reel.id)
  const liked = likes.has(reel.id)
  const { downloading, dlProgress, toast, startDownload } = useDownload()
  const [animKey, setAnimKey] = useState(0)

  // Replay staggered animations when slide becomes active
  useEffect(() => {
    if (isActive) setAnimKey((k) => k + 1)
  }, [isActive])

  // Always use a stock image — pick from general category if reel has no bg_image
  const baseURL = api.defaults.baseURL || ''
  const bgUrl = reel.bgImage
    || `${baseURL}/bg-images/general/${String((reel.id % 10) + 1).padStart(2, '0')}.jpg`

  return (
    <div className="flex items-center justify-center h-full bg-black">
      <DownloadToast {...toast} />
      <div className="relative w-full max-w-[480px] h-full overflow-hidden flex flex-col bg-[#0A0F1A]">
        {/* Stock image background */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${bgUrl})` }}
        />
        {/* Dark gradient overlay for text readability */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/80" />
        {/* Dot pattern overlay (subtle texture) */}
        <div
          className="absolute inset-0 gradient-shimmer pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.08) 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
        />

        {/* Content */}
        <div className="relative z-10 flex flex-col h-full p-6 md:p-8">
          {/* Title */}
          <h2
            key={`t-${animKey}`}
            className="text-2xl md:text-3xl font-bold font-display leading-tight text-white line-clamp-3 mb-4"
            style={{
              opacity: isActive ? 1 : 0,
              animation: isActive ? 'fadeUp 0.5s ease-out both' : 'none',
              animationDelay: '100ms',
            }}
          >
            {reel.title}
          </h2>

          {/* Separator */}
          <div
            key={`s-${animKey}`}
            className="w-16 h-px bg-white/25 mb-4"
            style={{
              opacity: isActive ? 1 : 0,
              animation: isActive ? 'fadeUp 0.5s ease-out both' : 'none',
              animationDelay: '200ms',
            }}
          />

          {/* Body */}
          <div
            key={`b-${animKey}`}
            className="flex-1 min-h-0"
            style={{
              opacity: isActive ? 1 : 0,
              animation: isActive ? 'fadeUp 0.5s ease-out both' : 'none',
              animationDelay: '300ms',
            }}
          >
            <p className="text-sm md:text-base leading-relaxed text-white/75 line-clamp-5">
              {reel.body}
            </p>
          </div>

          {/* Action bar */}
          <div
            key={`a-${animKey}`}
            className="flex items-center gap-3 mt-6 pt-4 border-t border-white/10"
            style={{
              opacity: isActive ? 1 : 0,
              animation: isActive ? 'slideUp 0.3s ease-out both' : 'none',
              animationDelay: '400ms',
            }}
          >
            <button
              onClick={() => toggleLike(reel.id)}
              className={`flex items-center gap-1.5 px-3 py-2.5 rounded-full text-sm font-medium transition-colors cursor-pointer ${
                liked
                  ? 'bg-red-500/20 text-red-500'
                  : 'bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white/80'
              }`}
            >
              {liked ? <HeartFill /> : <Heart />}
            </button>
            <button
              onClick={() => startDownload(reel, true)}
              disabled={downloading}
              className={`flex items-center gap-1.5 px-4 py-2.5 rounded-full text-sm font-medium transition-colors cursor-pointer backdrop-blur-sm ${
                downloading ? 'bg-primary/20 text-primary' : 'bg-white/10 hover:bg-white/20 text-white/80'
              }`}
            >
              <span className="relative inline-flex items-center justify-center w-[18px] h-[18px]">
                <Download />
                {downloading && <DownloadProgressRing progress={dlProgress} size={18} stroke={2} />}
              </span>
              {downloading ? `${dlProgress}%` : 'Download'}
            </button>
            <button
              onClick={() => toggleBookmark(reel.id)}
              className={`flex items-center gap-1.5 px-3 py-2.5 rounded-full text-sm font-medium transition-colors cursor-pointer ${
                saved
                  ? 'bg-white/20 text-white'
                  : 'bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white/80'
              }`}
            >
              {saved ? <BookmarkFill /> : <Bookmark />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

const TABS = [
  { id: 'explore', label: 'Explore' },
  { id: 'all', label: 'For You' },
]

export default function FeedPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { reels, setReels, appendReels, feedPage, hasMore } = useStore()
  const { onSlideEnter } = useReelTracker()
  const [initialLoading, setInitialLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [tab, setTab] = useState('explore')
  const [failedVideos, setFailedVideos] = useState(new Set())
  const [initialSlide, setInitialSlide] = useState(0)
  const bookNavState = useRef(location.state)
  const swiperRef = useRef(null)


  const loadReels = async (activeTab = tab) => {
    setInitialLoading(true)
    setError(false)
    try {
      const data = await getFeed(1, 200, null, activeTab)
      if (data.reels?.length) {
        const mapped = data.reels.map(mapReel)
        setReels(mapped)
        onSlideEnter(mapped[0].id)
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

  // Update Swiper when new reels arrive (e.g. via WebSocket reel_ready)
  useEffect(() => {
    if (swiperRef.current) swiperRef.current.update()
  }, [reels.length])

  // Load more when reaching end
  const handleReachEnd = async () => {
    if (!hasMore || loading) return
    setLoading(true)
    try {
      const data = await getFeed(feedPage + 1, 50, null, tab)
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
    <div className="feed-filter-tabs">
      {TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => handleTabChange(t.id)}
          className={`feed-filter-tab ${tab === t.id ? 'active' : ''}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )

  if (initialLoading) {
    return (
      <div className="h-full flex flex-col overflow-hidden">
        {tabBar}
        <div className="flex-1">
          <Spinner text="Loading bites..." />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full flex flex-col overflow-hidden">
        {tabBar}
        <div className="flex-1">
          <ErrorState onRetry={() => loadReels()} />
        </div>
      </div>
    )
  }

  if (reels.length === 0) {
    return (
      <div className="h-full flex flex-col overflow-hidden">
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
    <div className="h-full flex flex-col overflow-hidden">
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
        onSwiper={(swiper) => { swiperRef.current = swiper }}
        onReachEnd={handleReachEnd}
        onSlideChange={(swiper) => {
          setActiveIndex(swiper.activeIndex)
          const reel = reels[swiper.activeIndex]
          if (reel) onSlideEnter(reel.id)
        }}
      >
        {reels.map((reel, i) => {
          const showAsCard = (i + 1) % 4 === 0
          return (
            <SwiperSlide key={reel.id}>
              {showAsCard || !reel.videoUrl || failedVideos.has(reel.id) ? (
                <GradientPostCard reel={reel} index={i} total={reels.length} isActive={i === activeIndex} />
              ) : (
                <VideoReelCard reel={reel} index={i} total={reels.length} isActive={i === activeIndex} onVideoError={(id) => setFailedVideos(prev => new Set(prev).add(id))} />
              )}
            </SwiperSlide>
          )
        })}

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
