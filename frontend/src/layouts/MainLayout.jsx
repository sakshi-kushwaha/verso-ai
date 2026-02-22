import { Outlet, NavLink, Link } from 'react-router-dom'
import useStore from '../store/useStore'
import UploadTracker from '../components/UploadTracker'
import { Home, Bookmark, Upload, User, Book, Help } from '../components/Icons'
import './MainLayout.css'

function VersoLogo({ id = 'vg-ml' }) {
  return (
    <svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
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

const navItems = [
  { to: '/', icon: Home, label: 'Feed' },
  { to: '/books', icon: Book, label: 'My Collections' },
  { to: '/upload', icon: Upload, label: 'Upload' },
  { to: '/bookmarks', icon: Bookmark, label: 'Saved' },
]

const mobileNavItems = [
  { to: '/', icon: Home, label: 'Feed' },
  { to: '/books', icon: Book, label: 'Collections' },
  { to: '/upload', icon: Upload, label: 'Upload' },
  { to: '/bookmarks', icon: Bookmark, label: 'Saved' },
  { to: '/profile', icon: User, label: 'Profile' },
]

const sidebarLinkClass = ({ isActive }) => `nav-item ${isActive ? 'active' : ''}`
const mobileLinkClass = ({ isActive }) => `mob-nav-item ${isActive ? 'active' : ''}`

export default function MainLayout() {
  return (
    <div className="app-shell">
      {/* ═══ SIDEBAR ═══ */}
      <aside className="app-sidebar">
        <NavLink to="/" className="sidebar-logo">
          <VersoLogo id="vg-sidebar" />
        </NavLink>

        <nav className="sidebar-nav">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={sidebarLinkClass} end={to === '/'}>
              <Icon />
              <span className="tooltip">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-spacer" />

        <div className="sidebar-bottom">
          <NavLink to="/help" className={sidebarLinkClass}>
            <Help />
            <span className="tooltip">Help</span>
          </NavLink>
          <NavLink to="/profile" className={sidebarLinkClass}>
            <User />
            <span className="tooltip">Profile</span>
          </NavLink>
        </div>
      </aside>

      {/* ═══ MAIN ═══ */}
      <div className="app-main">
        <header className="app-topbar">
          <NavLink to="/" className="topbar-brand">
            <div className="topbar-brand-icon">
              <VersoLogo id="vg-topbar" />
            </div>
            <div className="topbar-brand-text">Verso <span>AI</span></div>
          </NavLink>

          <div className="topbar-spacer" />

          <Link to="/upload" className="topbar-upload">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Upload
          </Link>
        </header>

        <UploadTracker />

        <main className="app-content">
          <Outlet />
        </main>

        {/* ═══ MOBILE BOTTOM NAV ═══ */}
        <nav className="app-mobile-nav">
          {mobileNavItems.map(({ to, icon: Icon }) => (
            <NavLink key={to} to={to} className={mobileLinkClass} end={to === '/'}>
              <Icon />
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
