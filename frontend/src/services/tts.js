import { getAudio } from '../api'
import { getCachedAudio, cacheAudio } from './audioCache'

// Chrome loads voices asynchronously — cache them once ready
let _voicesLoaded = false
if (typeof window !== 'undefined' && window.speechSynthesis) {
  if (window.speechSynthesis.getVoices().length > 0) {
    _voicesLoaded = true
  }
  window.speechSynthesis.addEventListener('voiceschanged', () => {
    _voicesLoaded = window.speechSynthesis.getVoices().length > 0
  })
}

/**
 * Check if browser TTS is available and has voices loaded.
 */
export function isBrowserTtsReady() {
  return !!(window.speechSynthesis && _voicesLoaded)
}

/**
 * Split text into sentences for chunked utterance (avoids Chrome 15s bug).
 */
function splitSentences(text) {
  const parts = text.match(/[^.!?]+[.!?]+[\s]*/g)
  if (!parts) return [text]
  return parts.map((s) => s.trim()).filter(Boolean)
}

/**
 * Speak text using the browser's SpeechSynthesis API.
 * Chunks long text into sentences to avoid Chrome's ~15s cutoff.
 * Returns a controller { pause, resume, cancel }.
 */
export function speakBrowser(text, onEnd) {
  const synth = window.speechSynthesis
  const sentences = splitSentences(text)
  let cancelled = false
  let currentIndex = 0

  const voices = synth.getVoices()
  const englishVoice =
    voices.find((v) => v.lang.startsWith('en') && v.localService) ||
    voices.find((v) => v.lang.startsWith('en')) ||
    voices[0]

  function speakNext() {
    if (cancelled || currentIndex >= sentences.length) {
      if (!cancelled && onEnd) onEnd()
      return
    }
    const utt = new SpeechSynthesisUtterance(sentences[currentIndex])
    if (englishVoice) utt.voice = englishVoice
    utt.rate = 1.0
    utt.pitch = 1.0
    utt.onend = () => {
      currentIndex++
      speakNext()
    }
    utt.onerror = () => {
      if (!cancelled && onEnd) onEnd()
    }
    synth.speak(utt)
  }

  speakNext()

  return {
    pause: () => synth.pause(),
    resume: () => synth.resume(),
    cancel: () => {
      cancelled = true
      synth.cancel()
    },
  }
}

/**
 * Play audio from the server TTS endpoint (Piper neural / espeak).
 * Checks cache first, caches after fetch.
 * Returns a controller { pause, resume, cancel }.
 */
export async function speakServer(reelId, onEnd) {
  let blobUrl

  // Check cache first
  const cached = await getCachedAudio(reelId)
  if (cached) {
    blobUrl = cached
  } else {
    // getAudio returns a blob URL directly
    blobUrl = await getAudio(reelId)
    // Cache the blob for next time (non-blocking)
    cacheAudioFromUrl(reelId, blobUrl).catch(() => {})
  }

  const audio = new Audio(blobUrl)

  return new Promise((resolve, reject) => {
    audio.oncanplaythrough = () => {
      audio.play().catch(() => { if (onEnd) onEnd() })
      resolve({
        pause: () => audio.pause(),
        resume: () => audio.play(),
        cancel: () => {
          audio.pause()
          audio.currentTime = 0
        },
      })
    }
    audio.onended = () => { if (onEnd) onEnd() }
    audio.onerror = () => {
      if (onEnd) onEnd()
      reject(new Error('Audio load failed'))
    }
    audio.load()
  })
}

/** Helper: fetch blob from a blob URL and cache it. */
async function cacheAudioFromUrl(reelId, blobUrl) {
  try {
    const resp = await fetch(blobUrl)
    const blob = await resp.blob()
    await cacheAudio(reelId, blob)
  } catch {
    // Not critical
  }
}

/**
 * Main entry: browser TTS first (saves ~200-300MB server RAM by never loading Piper).
 * Falls back to server /audio/ endpoint only if browser has no voices.
 * Returns a controller { pause, resume, cancel }.
 */
export async function speak(reelId, text, onEnd) {
  // Browser TTS first — offloads server RAM entirely
  if (text && isBrowserTtsReady()) {
    return speakBrowser(text, onEnd)
  }
  // No browser voices — fall back to server TTS (Piper/espeak)
  return speakServer(reelId, onEnd)
}
