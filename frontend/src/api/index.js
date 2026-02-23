import axios from 'axios'

const baseURL = window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : `${window.location.origin}`

const api = axios.create({ baseURL, timeout: 30000 })

// Attach auth token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('verso_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Token refresh logic — silently refresh on 401
let isRefreshing = false
let refreshSubscribers = []

function onRefreshed(newToken) {
  refreshSubscribers.forEach((cb) => cb(newToken))
  refreshSubscribers = []
}

function clearAndRedirect() {
  localStorage.removeItem('verso_token')
  localStorage.removeItem('verso_refresh_token')
  localStorage.removeItem('verso_user')
  window.location.href = '/login'
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const refreshToken = localStorage.getItem('verso_refresh_token')
      if (!refreshToken) {
        clearAndRedirect()
        return Promise.reject(error)
      }
      if (!isRefreshing) {
        isRefreshing = true
        try {
          const { data } = await axios.post(`${baseURL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          localStorage.setItem('verso_token', data.token)
          localStorage.setItem('verso_refresh_token', data.refresh_token)
          isRefreshing = false
          onRefreshed(data.token)
          originalRequest.headers.Authorization = `Bearer ${data.token}`
          return api(originalRequest)
        } catch {
          isRefreshing = false
          clearAndRedirect()
          return Promise.reject(error)
        }
      } else {
        return new Promise((resolve) => {
          refreshSubscribers.push((newToken) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            resolve(api(originalRequest))
          })
        })
      }
    }
    return Promise.reject(error)
  }
)

// --- Auth ---
export async function signup(name, password, rememberMe = false) {
  const { data } = await api.post('/auth/signup', { name, password, remember_me: rememberMe })
  return data // { token, refresh_token, user: { id, name } }
}

export async function login(name, password, rememberMe = false) {
  const { data } = await api.post('/auth/login', { name, password, remember_me: rememberMe })
  return data // { token, refresh_token, user: { id, name } }
}

export async function getMe() {
  const { data } = await api.get('/auth/me')
  return data // { id, name, created_at }
}

export async function logoutApi(refreshToken) {
  try {
    await api.post('/auth/logout', { refresh_token: refreshToken })
  } catch { /* best-effort */ }
}

// --- Security Questions ---
export async function getPredefinedQuestions() {
  const { data } = await api.get('/auth/security-questions/predefined')
  return data.questions
}

export async function setSecurityQuestions(questions) {
  const { data } = await api.post('/auth/security-questions', { questions })
  return data
}

export async function getMySecurityQuestions() {
  const { data } = await api.get('/auth/security-questions')
  return data.questions
}

// --- Forgot Password ---
export async function forgotPasswordQuestions(username) {
  const { data } = await api.post('/auth/forgot-password/questions', { username })
  return data.questions
}

export async function forgotPasswordVerify(username, answers) {
  const { data } = await api.post('/auth/forgot-password/verify', { username, answers })
  return data.reset_token
}

export async function forgotPasswordReset(resetToken, newPassword) {
  const { data } = await api.post('/auth/forgot-password/reset', {
    reset_token: resetToken,
    new_password: newPassword,
  })
  return data
}

// --- Profile ---
export async function updateProfile(body) {
  const { data } = await api.put('/auth/profile', body)
  return data
}

export async function deleteAccount(password) {
  const { data } = await api.delete('/auth/account', { data: { password } })
  return data
}

// --- Sessions ---
export async function getSessions() {
  const { data } = await api.get('/auth/sessions')
  return data
}

export async function revokeSession(sessionId) {
  const { data } = await api.delete(`/auth/sessions/${sessionId}`)
  return data
}

export async function revokeAllSessions(refreshToken) {
  const { data } = await api.post('/auth/sessions/revoke-all', { refresh_token: refreshToken })
  return data
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
export async function getFeed(page = 1, limit = 5, uploadId = null, tab = null) {
  const params = { page, limit }
  if (uploadId) params.upload_id = uploadId
  if (tab) params.tab = tab
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

export async function deleteUpload(uploadId) {
  const { data } = await api.delete(`/upload/${uploadId}`)
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
  return data // { qa_ready, exchange_count, limit, remaining, has_summary }
}

export async function getChatSummary(uploadId) {
  const { data } = await api.get(`/chat/summary/${uploadId}`)
  return data // { summaries: [{ summary, session, created_at }] }
}

export async function startNewChatSession(uploadId) {
  const { data } = await api.post(`/chat/new-session/${uploadId}`)
  return data // { status, remaining }
}

// --- Document Summary ---
export async function getDocSummary(uploadId) {
  const { data } = await api.get(`/upload/${uploadId}/summary`, {
    timeout: 120000,
  })
  return data // { summary, generated }
}

export async function getSummaryAudio(uploadId) {
  const { data } = await api.get(`/audio/summary/${uploadId}`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(data)
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

// --- Interactions / Algorithm ---
export async function trackInteraction(reelId, action, timeSpentMs = 0) {
  const { data } = await api.post('/interactions/track', {
    reel_id: reelId,
    action,
    time_spent_ms: timeSpentMs,
  })
  return data
}

export async function getLikedReels() {
  const { data } = await api.get('/interactions/likes')
  return data
}

export default api
