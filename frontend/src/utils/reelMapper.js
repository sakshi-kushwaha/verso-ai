import api from '../api'

const ACCENTS = ['#3B82F6', '#06B6D4', '#F472B6', '#F59E0B', '#10B981', '#8B5CF6']

export function mapReel(r, i = null) {
  const accentIndex = i !== null ? i : r.id
  return {
    id: r.id,
    title: r.title,
    category: r.category || 'General',
    pages: r.page_ref || '—',
    body: r.summary || '',
    oneLiner: r.one_liner || r.title || '',
    narration: r.narration || r.summary || '',
    keywords: r.keywords ? r.keywords.split(',').map((k) => k.trim()).filter(Boolean) : [],
    accent: ACCENTS[accentIndex % ACCENTS.length],
    bgImage: r.bg_image ? `${api.defaults.baseURL}/${r.bg_image}` : null,
    videoUrl: r.video_path ? `${api.defaults.baseURL}/video/${r.id}` : null,
  }
}
