import { Outlet, NavLink } from 'react-router-dom'
import { Logo, Home, Cards, Chat, Bookmark, Chart, Logout } from '../components/Icons'

const navItems = [
  { to: '/', icon: Home, label: 'Feed' },
  { to: '/flashcards', icon: Cards, label: 'Cards' },
  { to: '/chat', icon: Chat, label: 'Chat' },
  { to: '/bookmarks', icon: Bookmark, label: 'Saved' },
  { to: '/progress', icon: Chart, label: 'Progress' },
]

const linkClass = ({ isActive }) =>
  `flex items-center justify-center w-10 h-10 rounded-xl transition-colors ${
    isActive ? 'text-primary bg-primary/10' : 'text-text-muted hover:text-primary'
  }`

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-bg">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 w-16 flex-col items-center py-6 bg-surface border-r border-border z-30">
        <Logo size={28} />
        <nav className="flex flex-col gap-2 mt-8">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={linkClass} title={label} end={to === '/'}>
              <Icon />
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto">
          <button className="flex items-center justify-center w-10 h-10 rounded-xl text-text-muted hover:text-danger transition-colors" title="Logout">
            <Logout />
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="md:ml-16 pb-18 md:pb-0 min-h-screen">
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 h-16 bg-surface border-t border-border flex items-center justify-around z-30">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={linkClass} title={label} end={to === '/'}>
            <Icon />
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
