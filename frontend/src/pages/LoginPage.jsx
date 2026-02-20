import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { signup, login } from '../api'
import useStore from '../store/useStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth } = useStore()
  const [tab, setTab] = useState('signin')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!username.trim() || !password.trim()) return
    setError('')
    setLoading(true)
    try {
      const data = tab === 'signup'
        ? await signup(username.trim(), password.trim())
        : await login(username.trim(), password.trim())
      setAuth(data.user, data.token)
      navigate('/')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Something went wrong'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSubmit()
  }

  return (
    <>
      {/* Tab toggle */}
      <div className="auth-tabs">
        {['signin', 'signup'].map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setError('') }}
            className={`auth-tab${tab === t ? ' active' : ''}`}
          >
            {t === 'signin' ? 'Login' : 'Sign Up'}
          </button>
        ))}
      </div>

      {error && <div className="auth-error">{error}</div>}

      {/* Username */}
      <div className="form-group">
        <label className="form-label">Username</label>
        <div className="input-wrapper">
          <div className="input-icon">
            <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
          </div>
          <input
            type="text"
            className="form-input"
            placeholder="Enter your username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
      </div>

      {/* Password */}
      <div className="form-group">
        <label className="form-label">Password</label>
        <div className="input-wrapper">
          <div className="input-icon">
            <svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
          </div>
          <input
            type={showPw ? 'text' : 'password'}
            className="form-input"
            style={{ paddingRight: '2.8rem' }}
            placeholder="Enter your password"
            autoComplete={tab === 'signup' ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            className="toggle-pw"
            onClick={() => setShowPw(!showPw)}
            type="button"
            aria-label="Toggle password visibility"
          >
            {showPw ? (
              <svg viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
            ) : (
              <svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
            )}
          </button>
        </div>
      </div>

      {/* Submit */}
      <button
        className="btn-submit"
        type="button"
        disabled={!username.trim() || !password.trim() || loading}
        onClick={handleSubmit}
      >
        <span>
          {loading ? 'Please wait...' : tab === 'signin' ? 'Login' : 'Create Account'}
          {!loading && (
            <svg viewBox="0 0 24 24"><path d="M5 12h14" /><path d="M12 5l7 7-7 7" /></svg>
          )}
        </span>
      </button>
    </>
  )
}
