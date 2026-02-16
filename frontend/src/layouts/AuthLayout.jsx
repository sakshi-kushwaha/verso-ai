import { Outlet } from 'react-router-dom'
import { Logo } from '../components/Icons'

export default function AuthLayout() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary-light/5 rounded-full blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: 'linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)',
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      <div className="w-full max-w-sm flex flex-col items-center gap-8 relative z-10 fade-up">
        <div className="flex items-center gap-3">
          <Logo size={36} />
          <span className="text-2xl font-bold font-display tracking-tight">Verso</span>
        </div>
        <div className="w-full bg-surface rounded-2xl p-6 border border-border shadow-xl shadow-primary/5">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
