import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
})

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

export default api
