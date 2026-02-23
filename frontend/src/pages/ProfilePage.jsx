import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { getMe, updateProfile, deleteAccount } from '../api'
import useStore from '../store/useStore'
import Button from '../components/Button'
import MobileBackButton from '../components/MobileBackButton'
import { Spinner, ErrorState } from '../components/StateScreens'
import { User, Help, ArrowR } from '../components/Icons'
import PasswordStrength from '../components/PasswordStrength'

export default function ProfilePage() {
  const navigate = useNavigate()
  const logout = useStore((s) => s.logout)
  const storeUser = useStore((s) => s.user)
  const displayName = useStore((s) => s.displayName)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  // Profile editing
  const [editName, setEditName] = useState('')
  const [editMsg, setEditMsg] = useState('')

  // Password change
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwLoading, setPwLoading] = useState(false)

  // Sessions section removed per request

  // Account deletion
  const [showDelete, setShowDelete] = useState(false)
  const [deletePw, setDeletePw] = useState('')
  const [deleteErr, setDeleteErr] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)

  const load = () => {
    setLoading(true)
    setError(false)
    getMe()
      .then((p) => {
        setProfile(p)
        setEditName(displayName || p.name || '')
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleSaveName = async () => {
    if (!editName.trim()) return
    try {
      await updateProfile({ display_name: editName.trim() })
      setEditMsg('Display name updated')
      // Update local store
      const completeOnboarding = useStore.getState().completeOnboarding
      const userRole = useStore.getState().userRole
      completeOnboarding(editName.trim(), userRole)
      setTimeout(() => setEditMsg(''), 2000)
    } catch {
      setEditMsg('Failed to update')
    }
  }

  const handleChangePassword = async () => {
    if (!currentPw || !newPw) return
    setPwMsg('')
    setPwLoading(true)
    try {
      await updateProfile({ current_password: currentPw, new_password: newPw })
      setPwMsg('Password changed successfully')
      setCurrentPw('')
      setNewPw('')
      setTimeout(() => setPwMsg(''), 3000)
    } catch (err) {
      setPwMsg(err.response?.data?.detail || 'Failed to change password')
    } finally {
      setPwLoading(false)
    }
  }

  // Sessions-related handlers removed

  const handleDeleteAccount = async () => {
    if (!deletePw) return
    setDeleteErr('')
    setDeleteLoading(true)
    try {
      await deleteAccount(deletePw)
      logout()
      navigate('/welcome')
    } catch (err) {
      setDeleteErr(err.response?.data?.detail || 'Failed to delete account')
    } finally {
      setDeleteLoading(false)
    }
  }

  if (loading) return <div className="max-w-xl mx-auto px-4 sm:px-6 pt-8 sm:pt-10"><Spinner text="Loading profile..." /></div>
  if (error) return <div className="max-w-xl mx-auto px-4 sm:px-6 pt-8 sm:pt-10"><ErrorState onRetry={load} /></div>

  const initial = (profile?.name || storeUser?.name || '?')[0].toUpperCase()
  const joined = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : '\u2014'

  return (
    <>
      <div className="max-w-xl mx-auto px-4 sm:px-6 pt-8 sm:pt-10 pb-20 sm:pb-6 fade-up">
        <MobileBackButton />
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
            { label: 'Uploads', value: profile.total_uploads, color: '#3B82F6' },
            { label: 'Bites', value: profile.total_reels, color: '#06B6D4' },
            { label: 'Flashcards', value: profile.total_flashcards, color: '#F472B6' },
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

        {/* Edit display name */}
        <div className="bg-surface rounded-xl p-5 border border-border mb-4">
          <h3 className="text-sm font-semibold mb-3">Display Name</h3>
          <div className="flex gap-2">
            <input
              type="text"
              className="flex-1 bg-bg rounded-lg px-3 py-2 text-sm border border-border outline-none focus:border-primary/30"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
            />
            <button
              className="px-4 py-2 bg-primary/10 text-primary text-sm font-semibold rounded-lg hover:bg-primary/20 transition-colors"
              onClick={handleSaveName}
              disabled={!editName.trim()}
            >
              Save
            </button>
          </div>
          {editMsg && <p className="text-xs mt-2 text-primary">{editMsg}</p>}
        </div>

        {/* Change password */}
        <div className="bg-surface rounded-xl p-5 border border-border mb-4">
          <h3 className="text-sm font-semibold mb-3">Change Password</h3>
          <input
            type="password"
            className="w-full bg-bg rounded-lg px-3 py-2 text-sm border border-border outline-none focus:border-primary/30 mb-2"
            placeholder="Current password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
          />
          <input
            type="password"
            className="w-full bg-bg rounded-lg px-3 py-2 text-sm border border-border outline-none focus:border-primary/30 mb-1"
            placeholder="New password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
          />
          {newPw && <PasswordStrength password={newPw} />}
          <button
            className="mt-3 w-full px-4 py-2 bg-primary/10 text-primary text-sm font-semibold rounded-lg hover:bg-primary/20 transition-colors disabled:opacity-40"
            onClick={handleChangePassword}
            disabled={!currentPw || !newPw || pwLoading}
          >
            {pwLoading ? 'Updating...' : 'Update Password'}
          </button>
          {pwMsg && (
            <p className={`text-xs mt-2 ${pwMsg.includes('success') ? 'text-green-400' : 'text-red-400'}`}>{pwMsg}</p>
          )}
        </div>

        {/* Active Sessions section removed */}

        {/* Help link */}
        <Link to="/help" className="flex items-center gap-3 bg-surface rounded-xl p-4 border border-border mb-6 hover:border-primary/30 transition-colors">
          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <Help />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold">Help & FAQ</p>
            <p className="text-text-muted text-xs">Frequently asked questions</p>
          </div>
          <span className="text-text-muted"><ArrowR /></span>
        </Link>

        {/* Logout */}
        <Button full variant="danger" onClick={() => setShowConfirm(true)} className="mt-4">
          Logout
        </Button>

        {/* Delete account */}
        <button
          className="w-full mt-3 py-2 text-xs text-text-muted hover:text-red-400 transition-colors"
          onClick={() => setShowDelete(true)}
        >
          Delete Account
        </button>
      </div>

      {/* Logout confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowConfirm(false)}>
          <div className="bg-surface rounded-2xl p-8 border border-border w-full max-w-xs mx-4 text-center fade-up shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold font-display mb-2">Logout</h3>
            <p className="text-text-muted text-sm mb-6">Are you sure you want to logout?</p>
            <div className="flex gap-3">
              <Button full variant="secondary" onClick={() => setShowConfirm(false)}>Cancel</Button>
              <Button full variant="danger" onClick={handleLogout}>Logout</Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete account modal */}
      {showDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => { setShowDelete(false); setDeleteErr(''); setDeletePw('') }}>
          <div className="bg-surface rounded-2xl p-8 border border-border w-full max-w-xs mx-4 text-center fade-up shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold font-display mb-2 text-red-400">Delete Account</h3>
            <p className="text-text-muted text-sm mb-4">This action is permanent and cannot be undone. Enter your password to confirm.</p>
            <input
              type="password"
              className="w-full bg-bg rounded-lg px-3 py-2 text-sm border border-border outline-none focus:border-red-400/30 mb-3"
              placeholder="Your password"
              value={deletePw}
              onChange={(e) => setDeletePw(e.target.value)}
            />
            {deleteErr && <p className="text-xs text-red-400 mb-3">{deleteErr}</p>}
            <div className="flex gap-3">
              <Button full variant="secondary" onClick={() => { setShowDelete(false); setDeleteErr(''); setDeletePw('') }}>Cancel</Button>
              <Button full variant="danger" onClick={handleDeleteAccount} disabled={!deletePw || deleteLoading}>
                {deleteLoading ? 'Deleting...' : 'Delete'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
