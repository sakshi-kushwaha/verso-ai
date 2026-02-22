import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import useStore from '../store/useStore'
import './OnboardingPage.css'

const ROLES = [
  { id: 'student', emoji: '\uD83C\uDF93', label: 'Student', desc: 'Studying for exams or courses' },
  { id: 'professional', emoji: '\uD83D\uDCBC', label: 'Professional', desc: 'Learning for work or career' },
  { id: 'reader', emoji: '\uD83D\uDCDA', label: 'Reading Lover', desc: 'Exploring topics out of curiosity' },
]

export default function OnboardingPage() {
  const navigate = useNavigate()
  const token = useStore((s) => s.token)
  const user = useStore((s) => s.user)
  const onboarded = useStore((s) => s.onboarded)
  const completeOnboarding = useStore((s) => s.completeOnboarding)

  const [step, setStep] = useState(1)
  const [name, setName] = useState(user?.name || '')
  const [selectedRole, setSelectedRole] = useState(null)

  if (!token) return <Navigate to="/login" replace />
  if (onboarded) return <Navigate to="/" replace />

  const handleContinue = () => {
    if (!name.trim()) return
    setStep(2)
  }

  const handleFinish = (roleId) => {
    setSelectedRole(roleId)
    completeOnboarding(name.trim(), roleId)
    navigate('/')
  }

  return (
    <div className="onboarding-page">
      <div className="onboarding-orbs">
        <div className="ob-orb ob-orb-1" />
        <div className="ob-orb ob-orb-2" />
      </div>

      <div className="onboarding-container">
        {/* Progress dots */}
        <div className="ob-progress">
          <div className={`ob-dot${step >= 1 ? ' active' : ''}`} />
          <div className={`ob-dot${step >= 2 ? ' active' : ''}`} />
        </div>

        {step === 1 && (
          <div className="ob-card ob-fade-in">
            <div className="ob-emoji">{'\uD83D\uDC4B'}</div>
            <h1 className="ob-title">What should we call you?</h1>
            <p className="ob-subtitle">This is how Verso will greet you.</p>
            <input
              type="text"
              className="ob-input"
              placeholder="Your name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleContinue()}
              autoFocus
            />
            <button
              className="ob-btn-primary"
              disabled={!name.trim()}
              onClick={handleContinue}
            >
              <span>
                Continue
                <svg viewBox="0 0 24 24"><path d="M5 12h14" /><path d="M12 5l7 7-7 7" /></svg>
              </span>
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="ob-card ob-fade-in">
            <div className="ob-emoji">{'\u2728'}</div>
            <h1 className="ob-title">What best describes you?</h1>
            <p className="ob-subtitle">We'll tailor your experience, {name.trim()}.</p>
            <div className="ob-roles">
              {ROLES.map((role) => (
                <button
                  key={role.id}
                  className={`ob-role-card${selectedRole === role.id ? ' selected' : ''}`}
                  onClick={() => handleFinish(role.id)}
                >
                  <span className="ob-role-emoji">{role.emoji}</span>
                  <div>
                    <div className="ob-role-label">{role.label}</div>
                    <div className="ob-role-desc">{role.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
