import { useRef, useCallback, useEffect } from 'react'
import { trackInteraction } from '../api'

const SKIP_THRESHOLD_MS = 2000

export default function useReelTracker() {
  const activeReel = useRef(null) // { reelId, startTime }

  const onSlideEnter = useCallback((reelId) => {
    // Flush previous reel
    if (activeReel.current) {
      const elapsed = Date.now() - activeReel.current.startTime
      const prevId = activeReel.current.reelId

      if (elapsed < SKIP_THRESHOLD_MS) {
        trackInteraction(prevId, 'skip', elapsed).catch(() => {})
      } else {
        trackInteraction(prevId, 'view', elapsed).catch(() => {})
      }
    }

    // Start tracking new reel
    activeReel.current = { reelId, startTime: Date.now() }
  }, [])

  const flush = useCallback(() => {
    if (activeReel.current) {
      const elapsed = Date.now() - activeReel.current.startTime
      const action = elapsed < SKIP_THRESHOLD_MS ? 'skip' : 'view'
      trackInteraction(activeReel.current.reelId, action, elapsed).catch(() => {})
      activeReel.current = null
    }
  }, [])

  // Flush on page visibility change or unmount
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) flush()
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility)
      flush()
    }
  }, [flush])

  return { onSlideEnter, flush }
}
