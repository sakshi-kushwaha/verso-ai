const CACHE_NAME = 'verso-audio-cache'
const MAX_ENTRIES = 50

/**
 * Get cached audio blob URL for a reel, or null if not cached.
 */
export async function getCachedAudio(reelId) {
  try {
    const cache = await caches.open(CACHE_NAME)
    const resp = await cache.match(`/audio/${reelId}`)
    if (!resp) return null
    const blob = await resp.blob()
    return URL.createObjectURL(blob)
  } catch {
    return null
  }
}

/**
 * Cache an audio blob for a reel. Enforces MAX_ENTRIES eviction (oldest first).
 */
export async function cacheAudio(reelId, blob) {
  try {
    const cache = await caches.open(CACHE_NAME)

    // Evict oldest entries if at capacity
    const keys = await cache.keys()
    if (keys.length >= MAX_ENTRIES) {
      const toEvict = keys.length - MAX_ENTRIES + 1
      for (let i = 0; i < toEvict; i++) {
        await cache.delete(keys[i])
      }
    }

    const response = new Response(blob, {
      headers: { 'Content-Type': blob.type || 'audio/wav' },
    })
    await cache.put(`/audio/${reelId}`, response)
  } catch {
    // Caching not available — not critical
  }
}

/**
 * Clear all cached audio.
 */
export async function clearAudioCache() {
  try {
    await caches.delete(CACHE_NAME)
  } catch {
    // Ignore
  }
}
