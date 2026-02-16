import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Input from '../components/Input'
import { User, Lock, Eye, EyeOff } from '../components/Icons'

export default function LoginPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('signin')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)

  const handleSubmit = () => {
    if (username.trim() && password.trim()) {
      navigate('/onboarding')
    }
  }

  return (
    <div className="fade-up">
      {/* Tab toggle */}
      <div className="flex bg-surface-alt rounded-lg p-1 mb-6">
        {['signin', 'signup'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 text-sm font-semibold rounded-md transition-all cursor-pointer ${
              tab === t
                ? 'bg-primary text-white shadow-md shadow-primary/25'
                : 'text-text-muted hover:text-text'
            }`}
          >
            {t === 'signin' ? 'Sign In' : 'Sign Up'}
          </button>
        ))}
      </div>

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
        disabled={!username.trim() || !password.trim()}
        className="mt-2"
      >
        {tab === 'signin' ? 'Sign In' : 'Create Account'}
      </Button>

      <p className="text-center text-text-muted text-xs mt-5">
        All data stays on your device
      </p>
    </div>
  )
}
