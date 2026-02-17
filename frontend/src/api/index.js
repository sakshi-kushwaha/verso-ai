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

// Fetch feed reels (paginated)
export async function getFeed(page = 1, limit = 5) {
  const { data } = await api.get('/feed', { params: { page, limit } })
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

// Save onboarding preferences (upsert)
export async function savePreferences(prefs, userId = 1) {
  const { data } = await api.put('/onboarding/preferences', prefs, {
    params: { user_id: userId },
  })
  return data // { status, user_id }
}

// Get onboarding preferences
export async function getPreferences(userId = 1) {
  const { data } = await api.get('/onboarding/preferences', {
    params: { user_id: userId },
  })
  return data
}

// List uploads
export async function getUploads() {
  const { data } = await api.get('/uploads')
  return data // [{ id, filename, status, qa_ready }]
}

// Chat Q&A
export async function askChat(uploadId, question, userId = 1) {
  const { data } = await api.post('/chat/ask', {
    upload_id: uploadId,
    question,
    user_id: userId,
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

export default api
