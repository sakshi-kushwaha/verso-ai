import { Outlet } from 'react-router-dom'
import './AuthLayout.css'

function VersoLogo({ id = 'vga', size = 36 }) {
  return (
    <svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" width={size} height={size}>
      <defs>
        <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#00e5ff" />
          <stop offset="100%" stopColor="#7c4dff" />
        </linearGradient>
      </defs>
      <ellipse cx="20" cy="20" rx="18" ry="10" fill="none" stroke={`url(#${id})`} strokeWidth="1.2" opacity="0.5" transform="rotate(-20 20 20)" />
      <path d="M10 10L20 32L30 10" fill="none" stroke={`url(#${id})`} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.85" />
      <circle cx="30.5" cy="11" r="3" fill={`url(#${id})`} />
    </svg>
  )
}

export default function AuthLayout() {
  return (
    <div className="auth-page">
      <div className="orb-container">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>
      <div className="grid-bg" />

      <div className="login-container">
        <div className="auth-logo-area">
          <div className="auth-logo-icon"><VersoLogo /></div>
          <div className="auth-logo-text">Verso <span>AI</span></div>
        </div>

        <div className="login-card">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
