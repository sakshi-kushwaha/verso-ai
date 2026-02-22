import { useNavigate } from 'react-router-dom'
import { ArrowL } from './Icons'

export default function MobileBackButton({ label = 'Back' }) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate(-1)}
      className="flex sm:hidden items-center gap-1.5 text-text-muted hover:text-primary text-sm mb-4 cursor-pointer transition-colors"
    >
      <ArrowL /> {label}
    </button>
  )
}
