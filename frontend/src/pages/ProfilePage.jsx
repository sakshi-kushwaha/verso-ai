import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe } from '../api'
import useStore from '../store/useStore'
import Button from '../components/Button'
import { Spinner, ErrorState } from '../components/StateScreens'
import { User } from '../components/Icons'

export default function ProfilePage() {
  const navigate = useNavigate()
  const logout = useStore((s) => s.logout)
  const storeUser = useStore((s) => s.user)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const load = () => {
    setLoading(true)
    setError(false)
    getMe()
      .then(setProfile)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  if (loading) return <div className="max-w-xl mx-auto p-6 pt-10"><Spinner text="Loading profile..." /></div>
  if (error) return <div className="max-w-xl mx-auto p-6 pt-10"><ErrorState onRetry={load} /></div>

  const initial = (profile?.name || storeUser?.name || '?')[0].toUpperCase()
  const joined = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : '—'

  return (
    <>
      <div className="max-w-xl mx-auto p-6 pt-10 fade-up">
        <h1 className="text-2xl font-bold font-display mb-1">Profile</h1>
        <p className="text-text-muted text-sm mb-8">Your account details</p>

        {/* Avatar + name */}
        <div className="bg-surface rounded-2xl p-8 border border-border flex flex-col items-center mb-6">
          <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center text-primary text-3xl font-bold font-display mb-4">
            {initial}
          </div>
          <h2 className="text-xl font-bold font-display">{profile.name}</h2>
          <p className="text-text-muted text-sm mt-1">Joined {joined}</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            { label: 'Uploads', value: profile.total_uploads, color: '#6366F1' },
            { label: 'Reels', value: profile.total_reels, color: '#8B5CF6' },
            { label: 'Flashcards', value: profile.total_flashcards, color: '#EC4899' },
          ].map((stat, i) => (
            <div
              key={i}
              className="bg-surface rounded-xl p-4 border border-border text-center fade-up"
              style={{ animationDelay: `${i * 0.1}s` }}
            >
              <p className="text-2xl font-bold font-display" style={{ color: stat.color }}>{stat.value}</p>
              <p className="text-text-muted text-xs font-semibold uppercase tracking-wide mt-1">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Logout */}
        <Button full variant="danger" onClick={() => setShowConfirm(true)} className="mt-4">
          Logout
        </Button>
      </div>

      {/* Confirmation modal — outside page container for proper full-screen overlay */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowConfirm(false)}>
          <div className="bg-surface rounded-2xl p-8 border border-border w-80 text-center fade-up shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold font-display mb-2">Logout</h3>
            <p className="text-text-muted text-sm mb-6">Are you sure you want to logout?</p>
            <div className="flex gap-3">
              <Button full variant="secondary" onClick={() => setShowConfirm(false)}>Cancel</Button>
              <Button full variant="danger" onClick={handleLogout}>Logout</Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
