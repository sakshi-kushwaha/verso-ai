import { useState, useEffect } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import useStore from '../store/useStore'
import { getPredefinedQuestions, setSecurityQuestions } from '../api'
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

  // Security questions state
  const [predefinedQs, setPredefinedQs] = useState([])
  const [sq1, setSq1] = useState('')
  const [sq1Answer, setSq1Answer] = useState('')
  const [sq2, setSq2] = useState('')
  const [sq2Answer, setSq2Answer] = useState('')
  const [sqError, setSqError] = useState('')
  const [sqLoading, setSqLoading] = useState(false)

  useEffect(() => {
    getPredefinedQuestions().then(setPredefinedQs).catch(() => {})
  }, [])

  if (!token) return <Navigate to="/login" replace />
  if (onboarded) return <Navigate to="/" replace />

  const handleContinue = () => {
    if (!name.trim()) return
    setStep(2)
  }

  const handleRoleSelect = (roleId) => {
    setSelectedRole(roleId)
    // Store role temporarily, move to security questions
    setStep(3)
  }

  const handleFinish = async () => {
    if (!sq1 || !sq1Answer.trim() || !sq2 || !sq2Answer.trim()) {
      setSqError('Please select 2 questions and provide answers')
      return
    }
    if (sq1 === sq2) {
      setSqError('Please choose two different questions')
      return
    }
    setSqError('')
    setSqLoading(true)
    try {
      await setSecurityQuestions([
        { question: sq1, answer: sq1Answer.trim() },
        { question: sq2, answer: sq2Answer.trim() },
      ])
    } catch {
      // Non-blocking — continue onboarding even if this fails
    }
    setSqLoading(false)
    completeOnboarding(name.trim(), selectedRole)
    navigate('/')
  }

  const handleSkipSecurity = () => {
    completeOnboarding(name.trim(), selectedRole)
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
          <div className={`ob-dot${step >= 3 ? ' active' : ''}`} />
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
                  onClick={() => handleRoleSelect(role.id)}
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

        {step === 3 && (
          <div className="ob-card ob-fade-in">
            <div className="ob-emoji">{'\uD83D\uDD12'}</div>
            <h1 className="ob-title">Security Questions</h1>
            <p className="ob-subtitle">Set up 2 questions to reset your password if you forget it.</p>

            {sqError && <div className="ob-error">{sqError}</div>}

            <div className="ob-sq-group">
              <label className="ob-sq-label">Question 1</label>
              <select className="ob-select" value={sq1} onChange={(e) => setSq1(e.target.value)}>
                <option value="">Choose a question...</option>
                {predefinedQs.filter((q) => q !== sq2).map((q) => (
                  <option key={q} value={q}>{q}</option>
                ))}
              </select>
              {sq1 && (
                <input
                  type="text"
                  className="ob-input ob-sq-input"
                  placeholder="Your answer"
                  value={sq1Answer}
                  onChange={(e) => setSq1Answer(e.target.value)}
                />
              )}
            </div>

            <div className="ob-sq-group">
              <label className="ob-sq-label">Question 2</label>
              <select className="ob-select" value={sq2} onChange={(e) => setSq2(e.target.value)}>
                <option value="">Choose a question...</option>
                {predefinedQs.filter((q) => q !== sq1).map((q) => (
                  <option key={q} value={q}>{q}</option>
                ))}
              </select>
              {sq2 && (
                <input
                  type="text"
                  className="ob-input ob-sq-input"
                  placeholder="Your answer"
                  value={sq2Answer}
                  onChange={(e) => setSq2Answer(e.target.value)}
                />
              )}
            </div>

            <button
              className="ob-btn-primary"
              disabled={!sq1 || !sq1Answer.trim() || !sq2 || !sq2Answer.trim() || sqLoading}
              onClick={handleFinish}
            >
              <span>{sqLoading ? 'Saving...' : 'Finish Setup'}</span>
            </button>
            <button className="ob-btn-skip" onClick={handleSkipSecurity} type="button">
              Skip for now
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
