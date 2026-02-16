import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ONBOARD } from '../data/mockData'
import { savePreferences } from '../api'
import useStore from '../store/useStore'
import Button from '../components/Button'
import Input from '../components/Input'
import { ArrowL, ArrowR, Check } from '../components/Icons'

const DEFAULTS = {
  display_name: '',
  learning_style: 'reading',
  content_depth: 'balanced',
  use_case: 'learning',
  flashcard_difficulty: 'medium',
}

const TOTAL_QUESTIONS = ONBOARD.length
const CONFIRM_STEP = TOTAL_QUESTIONS

export default function OnboardingPage() {
  const navigate = useNavigate()
  const setPreferences = useStore((s) => s.setPreferences)
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState({ ...DEFAULTS })
  const [saving, setSaving] = useState(false)

  const current = step < TOTAL_QUESTIONS ? ONBOARD[step] : null

  const updateAnswer = (key, value) => {
    setAnswers((prev) => ({ ...prev, [key]: value }))
  }

  const submitPreferences = async (prefs) => {
    setSaving(true)
    try {
      await savePreferences(prefs)
    } catch {
      // Graceful fallback — store in Zustand for the session
    }
    setPreferences(prefs)
    setSaving(false)
    setStep(CONFIRM_STEP)
  }

  const next = () => {
    if (step < TOTAL_QUESTIONS - 1) {
      setStep(step + 1)
    } else {
      // Last quiz step — fill defaults for any skipped answers, then save
      const merged = { ...DEFAULTS, ...answers }
      submitPreferences(merged)
    }
  }

  const back = () => {
    if (step > 0) setStep(step - 1)
  }

  // --- Confirmation screen ---
  if (step === CONFIRM_STEP) {
    const name = answers.display_name || 'there'
    const summaryItems = ONBOARD.filter((q) => q.type === 'select').map((q) => {
      const chosen = q.options.find((o) => o.value === answers[q.key])
      return { label: q.question.replace('?', ''), value: chosen ? `${chosen.emoji} ${chosen.label}` : 'Default' }
    })

    return (
      <div className="fade-up text-center">
        <div className="text-5xl mb-4">{'\u2728'}</div>
        <h2 className="text-2xl font-bold font-display mb-2">You're all set, {name}!</h2>
        <p className="text-text-muted text-sm mb-6">Here's a summary of your preferences</p>

        <div className="flex flex-col gap-2 mb-8 text-left">
          {summaryItems.map((item) => (
            <div key={item.label} className="flex items-center justify-between p-3 rounded-lg bg-surface-alt border border-border">
              <span className="text-xs text-text-muted">{item.label}</span>
              <span className="text-sm font-semibold">{item.value}</span>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-3">
          <Button full onClick={() => navigate('/upload')}>
            Upload your first document
            <ArrowR />
          </Button>
          <Button variant="ghost" onClick={() => setStep(0)}>
            Change preferences
          </Button>
        </div>
      </div>
    )
  }

  // --- Quiz steps ---
  const isTextStep = current.type === 'text'
  const canContinue = isTextStep ? answers[current.key]?.trim().length > 0 : true

  return (
    <div className="fade-up">
      {/* Progress bars */}
      <div className="flex gap-2 mb-6">
        {ONBOARD.map((_, i) => (
          <div key={i} className="flex-1 h-1 rounded-full bg-surface-alt overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-500"
              style={{ width: i <= step ? '100%' : '0%' }}
            />
          </div>
        ))}
      </div>

      {/* Step label */}
      <p className="text-[10px] font-bold text-primary-light uppercase tracking-widest mb-3">
        Step {step + 1} / {TOTAL_QUESTIONS}
      </p>

      {/* Question */}
      <h2 className="text-xl font-bold font-display mb-1">{current.question}</h2>
      <p className="text-text-muted text-sm mb-6">{current.subtitle}</p>

      {/* Input or option cards */}
      {isTextStep ? (
        <div className="mb-6">
          <Input
            placeholder={current.placeholder}
            value={answers[current.key]}
            onChange={(e) => updateAnswer(current.key, e.target.value)}
          />
        </div>
      ) : (
        <div className="flex flex-col gap-3 mb-6">
          {current.options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => updateAnswer(current.key, opt.value)}
              className={`flex items-center gap-4 p-4 rounded-xl border transition-all text-left cursor-pointer ${
                answers[current.key] === opt.value
                  ? 'border-primary bg-primary/10 shadow-md shadow-primary/10'
                  : 'border-border bg-surface-alt hover:border-primary/30'
              }`}
            >
              <span className="text-2xl">{opt.emoji}</span>
              <div className="flex-1">
                <p className="font-semibold text-sm">{opt.label}</p>
                <p className="text-text-muted text-xs">{opt.desc}</p>
              </div>
              {answers[current.key] === opt.value && (
                <span className="text-primary"><Check /></span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Navigation */}
      <div className="flex gap-3">
        {step > 0 && (
          <Button variant="secondary" onClick={back} className="px-4">
            <ArrowL />
          </Button>
        )}
        {!isTextStep && (
          <Button variant="ghost" onClick={next}>
            Skip
          </Button>
        )}
        <Button full onClick={next} disabled={saving || (isTextStep && !canContinue)}>
          {saving ? 'Saving...' : step === TOTAL_QUESTIONS - 1 ? 'Finish' : 'Continue'}
          {!saving && <ArrowR />}
        </Button>
      </div>
    </div>
  )
}
