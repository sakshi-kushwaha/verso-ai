import { useState, useCallback } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Logo, Cards, Chat, Volume, Play } from '../components/Icons'
import SplashScreen from '../components/SplashScreen'
import useStore from '../store/useStore'

const features = [
  { icon: Play, title: 'Bites', desc: 'Your documents transformed into short, engaging bites you can swipe through like social media.' },
  { icon: Cards, title: 'Flashcards', desc: 'Automatically generate flashcards from your study material.' },
  { icon: Volume, title: 'Audio Summaries', desc: 'Listen to AI-generated audio summaries of your documents.' },
  { icon: Chat, title: 'Smart Chat', desc: 'Chat with AI about your documents to deepen understanding.' },
]

export default function LandingPage() {
  const token = useStore((s) => s.token)
  const [splashDone, setSplashDone] = useState(false)
  const handleSplashFinish = useCallback(() => setSplashDone(true), [])

  if (token) return <Navigate to="/" replace />

  if (!splashDone) return <SplashScreen onFinish={handleSplashFinish} />

  return (
    <div className="min-h-screen bg-bg text-text relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-20 left-1/4 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-20 right-1/4 w-[400px] h-[400px] bg-primary-light/5 rounded-full blur-[100px]" />
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: 'linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)',
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-6 md:px-12 py-5">
        <div className="flex items-center gap-2">
          <Logo size={32} />
          <span className="text-xl font-bold font-display tracking-tight">
            Verso <span className="text-primary">AI</span>
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-white transition-colors"
          >
            Log In
          </Link>
          <Link
            to="/signup"
            className="px-5 py-2 text-sm font-semibold bg-primary text-white rounded-xl hover:bg-primary-dark transition-colors shadow-md shadow-primary/25"
          >
            Sign Up
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 flex flex-col items-center text-center px-6 pt-16 md:pt-28 pb-16 fade-up">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-medium mb-6">
          AI-Powered Learning Platform
        </div>
        <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold font-display tracking-tight leading-tight max-w-3xl">
          Learn Smarter with{' '}
          <span className="text-primary">Verso AI</span>
        </h1>
        <p className="mt-5 text-text-muted text-base md:text-lg max-w-xl leading-relaxed">
          Upload your documents and watch AI turn them into bites, flashcards, audio summaries, and more — so you can study faster and retain more.
        </p>
        <div className="mt-10">
          <Link
            to="/signup"
            className="px-8 py-3 font-semibold bg-primary text-white rounded-xl hover:bg-primary-dark transition-colors shadow-lg shadow-primary/25 text-sm"
          >
            Get Started
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="relative z-10 px-6 md:px-12 pb-24">
        <div className="max-w-4xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-5">
          {features.map(({ icon: Icon, title, desc }, i) => (
            <div
              key={title}
              className="bg-surface rounded-2xl p-6 border border-border hover:border-primary/20 transition-colors fade-up"
              style={{ animationDelay: `${i * 0.1}s` }}
            >
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary mb-4">
                <Icon />
              </div>
              <h3 className="font-semibold font-display text-base mb-1">{title}</h3>
              <p className="text-text-muted text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 text-center py-8 text-text-muted text-xs border-t border-border">
        &copy; 2026 Verso AI. All rights reserved.
      </footer>
    </div>
  )
}
