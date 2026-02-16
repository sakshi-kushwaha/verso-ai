import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ONBOARD } from '../data/mockData'
import Button from '../components/Button'
import { ArrowL, ArrowR } from '../components/Icons'

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [selections, setSelections] = useState({})
  const current = ONBOARD[step]

  const select = (idx) => {
    setSelections((prev) => ({ ...prev, [step]: idx }))
  }

  const next = () => {
    if (step < ONBOARD.length - 1) {
      setStep(step + 1)
    } else {
      navigate('/upload')
    }
  }

  const back = () => {
    if (step > 0) setStep(step - 1)
  }

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
        Step {step + 1} / {ONBOARD.length}
      </p>

      {/* Question */}
      <h2 className="text-xl font-bold font-display mb-1">{current.question}</h2>
      <p className="text-text-muted text-sm mb-6">{current.subtitle}</p>

      {/* Options */}
      <div className="flex flex-col gap-3 mb-6">
        {current.options.map((opt, i) => (
          <button
            key={i}
            onClick={() => select(i)}
            className={`flex items-center gap-4 p-4 rounded-xl border transition-all text-left cursor-pointer ${
              selections[step] === i
                ? 'border-primary bg-primary/10 shadow-md shadow-primary/10'
                : 'border-border bg-surface-alt hover:border-primary/30'
            }`}
          >
            <span className="text-2xl">{opt.emoji}</span>
            <div>
              <p className="font-semibold text-sm">{opt.label}</p>
              <p className="text-text-muted text-xs">{opt.desc}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Navigation */}
      <div className="flex gap-3">
        {step > 0 && (
          <Button variant="secondary" onClick={back} className="px-4">
            <ArrowL />
          </Button>
        )}
        <Button variant="ghost" onClick={next}>
          Skip
        </Button>
        <Button full onClick={next}>
          {step === ONBOARD.length - 1 ? 'Start Learning' : 'Continue'}
          <ArrowR />
        </Button>
      </div>
    </div>
  )
}
