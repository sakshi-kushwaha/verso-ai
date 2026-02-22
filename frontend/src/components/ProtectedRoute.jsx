import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import useStore from '../store/useStore'

export default function ProtectedRoute() {
  const token = useStore((s) => s.token)
  const onboarded = useStore((s) => s.onboarded)
  const loadBookmarks = useStore((s) => s.loadBookmarks)
  const loadLikes = useStore((s) => s.loadLikes)

  useEffect(() => {
    if (token) {
      loadBookmarks()
      loadLikes()
    }
  }, [token])

  if (!token) return <Navigate to="/welcome" replace />
  if (!onboarded) return <Navigate to="/onboarding" replace />
  return <Outlet />
}
