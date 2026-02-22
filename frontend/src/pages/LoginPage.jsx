import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { signup, login, forgotPasswordQuestions, forgotPasswordVerify, forgotPasswordReset } from '../api'
import useStore from '../store/useStore'
import PasswordStrength from '../components/PasswordStrength'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth } = useStore()
  const [tab, setTab] = useState('signin')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Forgot password state
  const [forgotStep, setForgotStep] = useState(null) // null | 'username' | 'questions' | 'reset' | 'done'
  const [forgotUsername, setForgotUsername] = useState('')
  const [forgotQuestions, setForgotQuestions] = useState([])
  const [forgotAnswers, setForgotAnswers] = useState({})
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const handleSubmit = async () => {
    if (!username.trim() || !password.trim()) return
    setError('')
    setLoading(true)
    try {
      const data = tab === 'signup'
        ? await signup(username.trim(), password.trim(), rememberMe)
        : await login(username.trim(), password.trim(), rememberMe)
      setAuth(data.user, data.token, data.refresh_token)
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

  // ── Forgot password handlers ──
  const handleForgotLookup = async () => {
    if (!forgotUsername.trim()) return
    setError('')
    setLoading(true)
    try {
      const questions = await forgotPasswordQuestions(forgotUsername.trim())
      setForgotQuestions(questions)
      setForgotAnswers({})
      setForgotStep('questions')
    } catch (err) {
      setError(err.response?.data?.detail || 'User not found')
    } finally {
      setLoading(false)
    }
  }

  const handleForgotVerify = async () => {
    setError('')
    setLoading(true)
    try {
      const answers = forgotQuestions.map((q) => ({
        question_id: q.id,
        answer: forgotAnswers[q.id] || '',
      }))
      const token = await forgotPasswordVerify(forgotUsername.trim(), answers)
      setResetToken(token)
      setForgotStep('reset')
    } catch (err) {
      setError(err.response?.data?.detail || 'Incorrect answers')
    } finally {
      setLoading(false)
    }
  }

  const handleForgotReset = async () => {
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setError('')
    setLoading(true)
    try {
      await forgotPasswordReset(resetToken, newPassword)
      setForgotStep('done')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reset password')
    } finally {
      setLoading(false)
    }
  }

  const exitForgot = () => {
    setForgotStep(null)
    setForgotUsername('')
    setForgotQuestions([])
    setForgotAnswers({})
    setResetToken('')
    setNewPassword('')
    setConfirmPassword('')
    setError('')
  }

  // ── Forgot password flow UI ──
  if (forgotStep) {
    return (
      <div className="forgot-flow">
        <button className="forgot-back" onClick={exitForgot} type="button">
          <svg viewBox="0 0 24 24" width="18" height="18"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
          Back to Login
        </button>

        <h2 className="forgot-title">
          {forgotStep === 'username' && 'Reset Password'}
          {forgotStep === 'questions' && 'Security Questions'}
          {forgotStep === 'reset' && 'Set New Password'}
          {forgotStep === 'done' && 'Password Reset!'}
        </h2>

        {error && <div className="auth-error">{error}</div>}

        {forgotStep === 'username' && (
          <>
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
                  value={forgotUsername}
                  onChange={(e) => setForgotUsername(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleForgotLookup()}
                />
              </div>
            </div>
            <button
              className="btn-submit"
              type="button"
              disabled={!forgotUsername.trim() || loading}
              onClick={handleForgotLookup}
            >
              <span>{loading ? 'Looking up...' : 'Continue'}</span>
            </button>
          </>
        )}

        {forgotStep === 'questions' && (
          <>
            {forgotQuestions.map((q) => (
              <div className="form-group" key={q.id}>
                <label className="form-label">{q.question}</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Your answer"
                    value={forgotAnswers[q.id] || ''}
                    onChange={(e) => setForgotAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  />
                </div>
              </div>
            ))}
            <button
              className="btn-submit"
              type="button"
              disabled={forgotQuestions.some((q) => !forgotAnswers[q.id]?.trim()) || loading}
              onClick={handleForgotVerify}
            >
              <span>{loading ? 'Verifying...' : 'Verify Answers'}</span>
            </button>
          </>
        )}

        {forgotStep === 'reset' && (
          <>
            <div className="form-group">
              <label className="form-label">New Password</label>
              <div className="input-wrapper">
                <input
                  type="password"
                  className="form-input"
                  placeholder="New password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>
              <PasswordStrength password={newPassword} />
            </div>
            <div className="form-group">
              <label className="form-label">Confirm Password</label>
              <div className="input-wrapper">
                <input
                  type="password"
                  className="form-input"
                  placeholder="Confirm password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
            </div>
            <button
              className="btn-submit"
              type="button"
              disabled={!newPassword || !confirmPassword || loading}
              onClick={handleForgotReset}
            >
              <span>{loading ? 'Resetting...' : 'Reset Password'}</span>
            </button>
          </>
        )}

        {forgotStep === 'done' && (
          <>
            <p className="forgot-success">Your password has been reset. You can now log in with your new password.</p>
            <button className="btn-submit" type="button" onClick={exitForgot}>
              <span>Back to Login</span>
            </button>
          </>
        )}
      </div>
    )
  }

  // ── Main login/signup UI ──
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
            disabled={loading}
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
            disabled={loading}
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
        {tab === 'signup' && <PasswordStrength password={password} />}
      </div>

      {/* Remember me + Forgot password */}
      <div className="auth-options">
        <label className="remember-me">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          <span>Remember me</span>
        </label>
        {tab === 'signin' && (
          <button
            className="forgot-link"
            type="button"
            onClick={() => setForgotStep('username')}
          >
            Forgot password?
          </button>
        )}
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
