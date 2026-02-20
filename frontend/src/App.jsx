import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import AuthLayout from './layouts/AuthLayout'
import ProtectedRoute from './components/ProtectedRoute'
import FeedPage from './pages/FeedPage'
import BookmarksPage from './pages/BookmarksPage'
import UploadPage from './pages/UploadPage'

import FlashcardsPage from './pages/FlashcardsPage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import MyBooksPage from './pages/MyBooksPage'
import ProfilePage from './pages/ProfilePage'
import LandingPage from './pages/LandingPage'

function App() {
  return (
    <Routes>
      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<FeedPage />} />
          <Route path="/bookmarks" element={<BookmarksPage />} />
          <Route path="/upload" element={<UploadPage />} />

          <Route path="/flashcards" element={<FlashcardsPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/books" element={<MyBooksPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
      </Route>
      <Route path="/welcome" element={<LandingPage />} />
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Route>
    </Routes>
  )
}

export default App
