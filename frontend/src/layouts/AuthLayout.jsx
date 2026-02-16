import { Outlet } from 'react-router-dom'
import { Logo } from '../components/Icons'

export default function AuthLayout() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm flex flex-col items-center gap-8">
        <Logo size={36} />
        <div className="w-full bg-surface rounded-2xl p-6 border border-border">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
