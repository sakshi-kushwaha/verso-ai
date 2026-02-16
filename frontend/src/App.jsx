import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import AuthLayout from './layouts/AuthLayout'
import FeedPage from './pages/FeedPage'
import BookmarksPage from './pages/BookmarksPage'
import UploadPage from './pages/UploadPage'
import ProgressPage from './pages/ProgressPage'
import FlashcardsPage from './pages/FlashcardsPage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import OnboardingPage from './pages/OnboardingPage'

function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<FeedPage />} />
        <Route path="/bookmarks" element={<BookmarksPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/flashcards" element={<FlashcardsPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Route>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
      </Route>
    </Routes>
  )
}

export default App
