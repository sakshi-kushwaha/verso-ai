import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import useStore from '../store/useStore'

export default function ProtectedRoute() {
  const token = useStore((s) => s.token)
  const loadBookmarks = useStore((s) => s.loadBookmarks)

  useEffect(() => {
    if (token) loadBookmarks()
  }, [token])

  if (!token) return <Navigate to="/login" replace />
  return <Outlet />
}
