import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { signup, login } from '../api'
import useStore from '../store/useStore'
import Button from '../components/Button'
import Input from '../components/Input'
import { User, Lock, Eye, EyeOff } from '../components/Icons'

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

      if (tab === 'signup') {
        navigate('/onboarding')
      } else {
        navigate('/')
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Something went wrong'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fade-up">
      {/* Tab toggle */}
      <div className="flex bg-surface-alt rounded-lg p-1 mb-6">
        {['signin', 'signup'].map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setError('') }}
            className={`flex-1 py-2 text-sm font-semibold rounded-md transition-all cursor-pointer ${
              tab === t
                ? 'bg-primary text-white shadow-md shadow-primary/25'
                : 'text-text-muted hover:text-text'
            }`}
          >
            {t === 'signin' ? 'Login' : 'Sign Up'}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/10 text-danger text-sm">
          {error}
        </div>
      )}

      <Input
        label="Username"
        placeholder="Enter your username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        iconL={<User />}
      />

      <Input
        label="Password"
        type={showPw ? 'text' : 'password'}
        placeholder="Enter your password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        iconL={<Lock />}
        iconR={showPw ? <EyeOff /> : <Eye />}
        onIconR={() => setShowPw(!showPw)}
      />

      <Button
        full
        onClick={handleSubmit}
        disabled={!username.trim() || !password.trim() || loading}
        className="mt-2"
      >
        {loading ? 'Please wait...' : tab === 'signin' ? 'Login' : 'Create Account'}
      </Button>

    </div>
  )
}
