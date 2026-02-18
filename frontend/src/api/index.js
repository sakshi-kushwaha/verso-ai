import axios from 'axios'

const api = axios.create({
  baseURL: window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : `${window.location.origin}`,
  timeout: 30000,
})

// Attach auth token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('verso_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-redirect to login on 401 (expired/invalid token)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('verso_token')
      localStorage.removeItem('verso_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// --- Auth ---
export async function signup(name, password) {
  const { data } = await api.post('/auth/signup', { name, password })
  return data // { token, user: { id, name } }
}

export async function login(name, password) {
  const { data } = await api.post('/auth/login', { name, password })
  return data // { token, user: { id, name } }
}

export async function getMe() {
  const { data } = await api.get('/auth/me')
  return data // { id, name, created_at }
}

// Upload a document (PDF/DOCX)
export async function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data // { upload_id, status }
}

// Poll upload processing status
export async function getUploadStatus(uploadId) {
  const { data } = await api.get(`/upload/status/${uploadId}`)
  return data // { status, progress, reels_count }
}

// Fetch feed reels (paginated, optional upload_id filter)
export async function getFeed(page = 1, limit = 5, uploadId = null) {
  const params = { page, limit }
  if (uploadId) params.upload_id = uploadId
  const { data } = await api.get('/feed', { params })
  return data // { reels: [], total, page }
}

// Get audio for a reel (returns blob URL)
export async function getAudio(reelId) {
  const { data } = await api.get(`/audio/${reelId}`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(data)
}

// Fetch flashcards
export async function getFlashcards(uploadId) {
  const { data } = await api.get('/flashcards', {
    params: uploadId ? { upload_id: uploadId } : {},
  })
  return data
}

// List uploads (includes reel_count, flashcard_count, doc_type, total_pages)
export async function getUploads() {
  const { data } = await api.get('/uploads')
  return data
}

// Chat Q&A
export async function askChat(uploadId, question) {
  const { data } = await api.post('/chat/ask', {
    upload_id: uploadId,
    question,
  }, { timeout: 120000 })
  return data // { answer, sources, exchange_count, limit }
}

export async function getChatHistory(uploadId) {
  const { data } = await api.get(`/chat/history/${uploadId}`)
  return data // [{ id, user_message, ai_response, sources, created_at }]
}

export async function getChatStatus(uploadId) {
  const { data } = await api.get(`/chat/status/${uploadId}`)
  return data // { qa_ready, exchange_count, limit, remaining }
}

// --- Bookmarks ---
export async function getBookmarks() {
  const { data } = await api.get('/bookmarks')
  return data
}

export async function addBookmark(reelId, flashcardId) {
  const body = {}
  if (reelId) body.reel_id = reelId
  if (flashcardId) body.flashcard_id = flashcardId
  const { data } = await api.post('/bookmarks', body)
  return data
}

export async function removeBookmark(bookmarkId) {
  const { data } = await api.delete(`/bookmarks/${bookmarkId}`)
  return data
}

// --- Progress ---
export async function recordView(uploadId, reelId) {
  const { data } = await api.post('/progress/view', { upload_id: uploadId, reel_id: reelId })
  return data
}

export async function getProgress(uploadId) {
  const { data } = await api.get(`/progress/${uploadId}`)
  return data
}

export async function getAllProgress() {
  const { data } = await api.get('/progress')
  return data
}

export default api
