import { useState, useEffect, useRef } from 'react'
import { Navigate, Link } from 'react-router-dom'
import useStore from '../store/useStore'
import './LandingPage.css'

/* ── Rising particles data (randomised once at module level) ── */
const PARTICLES = Array.from({ length: 25 }, (_, i) => ({
  id: i,
  left: `${Math.random() * 100}%`,
  size: 2 + Math.random() * 3,
  duration: 8 + Math.random() * 14,
  delay: Math.random() * 12,
  opacity: 0.25 + Math.random() * 0.45,
}))

/* ── Inline SVG: Verso V-logo ── */
function VersoLogo({ id = 'vg0', size = 40 }) {
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

/* ── SVG Icon helper (stroke-based, like the HTML <use> icons) ── */
const strokeStyle = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }
const sideStrokeStyle = { fill: 'none', stroke: '#ccc', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }

function IcoHome(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1h-2z" {...strokeStyle} /></svg> }
function IcoDoc(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" {...strokeStyle} /></svg> }
function IcoUpload(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" {...strokeStyle} /></svg> }
function IcoBookmark(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" {...strokeStyle} /></svg> }
function IcoHelp(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" {...strokeStyle} /></svg> }
function IcoUser(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" {...strokeStyle} /></svg> }
function IcoDownload(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" {...sideStrokeStyle} /></svg> }
function IcoBookmarkSide(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" {...sideStrokeStyle} /></svg> }
function IcoMute(props) { return <svg viewBox="0 0 24 24" {...props}><path d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /><path d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" /></svg> }

export default function LandingPage() {
  const token = useStore((s) => s.token)
  const [splashHidden, setSplashHidden] = useState(false)
  const [navScrolled, setNavScrolled] = useState(false)
  const navRef = useRef(null)

  // Auth redirect
  if (token) return <Navigate to="/" replace />

  // Splash timer
  useEffect(() => {
    const t = setTimeout(() => setSplashHidden(true), 3200)
    return () => clearTimeout(t)
  }, [])

  // Scroll listener for navbar
  useEffect(() => {
    const onScroll = () => setNavScrolled(window.scrollY > 50)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // IntersectionObserver for reveal animations
  useEffect(() => {
    const els = document.querySelectorAll('.reveal')
    const obs = new IntersectionObserver(
      (entries) => { entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('visible') }) },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
    )
    els.forEach((el) => obs.observe(el))
    return () => obs.disconnect()
  }, [splashHidden])

  return (
    <div className="landing-page">

      {/* ═══ SPLASH SCREEN ═══ */}
      <div className={`splash${splashHidden ? ' hidden' : ''}`}>
        <svg className="splash-logo" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="vgs" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00e5ff" />
              <stop offset="100%" stopColor="#7c4dff" />
            </linearGradient>
          </defs>
          <ellipse className="splash-orbit" cx="40" cy="40" rx="36" ry="20" fill="none" stroke="url(#vgs)" strokeWidth="1.5" opacity="0.45" transform="rotate(-20 40 40)" strokeDasharray="8 6" />
          <path d="M20 18L40 64L60 18" fill="none" stroke="url(#vgs)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
          <circle cx="61" cy="20" r="5" fill="url(#vgs)" />
        </svg>
        <div className="splash-text">Verso <span>AI</span></div>
        <div className="splash-tagline">Every document has a story. We make it scroll.</div>
      </div>

      {/* ═══ BACKGROUND ORBS ═══ */}
      <div className="orb-container">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>

      {/* ═══ RISING PARTICLES ═══ */}
      <div className="particles-bg">
        {PARTICLES.map((p) => (
          <div
            key={p.id}
            className="rise-dot"
            style={{
              left: p.left,
              width: p.size,
              height: p.size,
              opacity: p.opacity,
              animationDuration: `${p.duration}s`,
              animationDelay: `${p.delay}s`,
            }}
          />
        ))}
      </div>

      {/* ═══ NAV ═══ */}
      <nav ref={navRef} className={`landing-nav${navScrolled ? ' scrolled' : ''}`}>
        <div className="logo">
          <div className="logo-icon"><VersoLogo id="vg1" size={32} /></div>
          <div className="logo-text">Verso <span>AI</span></div>
        </div>
        <ul className="nav-links">
          <li><a href="#problem">Problem</a></li>
          <li><a href="#how">How It Works</a></li>
          <li><a href="#features">Features</a></li>
          <li><a href="#local">Local AI</a></li>
          <li><Link to="/login" className="nav-cta">Try Verso</Link></li>
        </ul>
      </nav>

      {/* ═══ HERO ═══ */}
      <section className="hero">
        <div className="hero-badge"><span className="dot" />100% Local AI — Your Data Never Leaves Your Device</div>
        <h1>Learn Smarter,<br /><span className="gradient-text">Scroll Better.</span></h1>
        <p className="hero-sub">
          Verso AI — An app that transforms documents into reels-style learning. Swipeable summaries,
          flashcards, audio narration, and AI chat — so you absorb more from every page. Fully local,
          fully private, entirely yours.
        </p>
        <div className="hero-actions">
          <Link to="/login" className="btn-primary"><span>Upload a Document &rarr;</span></Link>
          <a href="#how" className="btn-secondary">See How It Works</a>
        </div>

        {/* ── DEVICE MOCKUPS ── */}
        <div className="hero-mockup">

          {/* LAPTOP */}
          <div className="laptop-frame">
            <div className="laptop-screen">
              <div className="laptop-camera" />
              <div className="laptop-viewport">
                {/* Sidebar */}
                <div className="dt-sidebar">
                  <div className="dt-logo-area">
                    <div className="dt-logo-icon"><VersoLogo id="vg2" size={22} /></div>
                  </div>
                  <div className="dt-nav-icon active"><IcoHome /></div>
                  <div className="dt-nav-icon"><IcoDoc /></div>
                  <div className="dt-nav-icon"><IcoUpload /></div>
                  <div className="dt-nav-icon"><IcoBookmark /></div>
                  <div className="dt-spacer" />
                  <div className="dt-nav-icon"><IcoHelp /></div>
                  <div className="dt-nav-icon"><IcoUser /></div>
                </div>
                {/* Main reel area */}
                <div className="dt-main">
                  <div className="dt-reel-area">
                    <div className="scene-bg scene-photosynthesis">
                      <div className="star" /><div className="star" /><div className="star" />
                      <div className="star" /><div className="star" /><div className="star" />
                      <div className="sun" />
                      <div className="leaf leaf-1" />
                      <div className="leaf leaf-2" />
                      <div className="leaf leaf-3" />
                      <div className="leaf-vein" />
                      <div className="particles">
                        <div className="particle" /><div className="particle" /><div className="particle" />
                        <div className="particle" /><div className="particle" />
                      </div>
                    </div>
                    <div className="vid-text-overlay">sunlight into chemical energy through chlorophyll</div>
                    <div className="play-btn" />
                    <div className="mute-btn"><IcoMute /></div>
                    <div className="side-actions">
                      <div className="side-btn"><IcoDownload /></div>
                      <div className="side-btn"><IcoBookmarkSide /></div>
                    </div>
                    <div className="reel-info">
                      <div className="reel-cat green">Biology</div>
                      <div className="reel-ttl">Photosynthesis — How Plants Power the Planet</div>
                      <div className="reel-desc">Plants convert sunlight, water, and CO&#8322; into glucose and oxygen through photosynthesis — the process that sustains nearly all life on Earth...</div>
                    </div>
                    <div className="reel-progress"><div className="reel-progress-fill" /></div>
                  </div>
                </div>
              </div>
            </div>
            <div className="laptop-base" />
          </div>

          {/* PHONE */}
          <div className="phone-wrapper">
            <div className="phone-frame">
              <div className="phone-notch" />
              <div className="phone-screen">
                <div className="ph-topbar">
                  <div className="ph-logo-icon"><VersoLogo id="vg3" size={16} /></div>
                  <div className="ph-logo-text">Verso <span>AI</span></div>
                </div>
                <div className="ph-reel">
                  <div className="scene-bg scene-history">
                    <div className="h-star" /><div className="h-star" /><div className="h-star" />
                    <div className="h-star" /><div className="h-star" />
                    <div className="glow" />
                    <div className="pyramid" />
                    <div className="pyramid-2" />
                    <div className="sand" />
                  </div>
                  <div className="vid-text-overlay">built over twenty years using 2.3 million blocks</div>
                  <div className="play-btn" />
                  <div className="mute-btn"><IcoMute /></div>
                  <div className="side-actions">
                    <div className="side-btn"><IcoDownload /></div>
                    <div className="side-btn"><IcoBookmarkSide /></div>
                  </div>
                  <div className="reel-info">
                    <div className="reel-cat amber">History</div>
                    <div className="reel-ttl">The Great Pyramid — Engineering the Impossible</div>
                    <div className="reel-desc">The Great Pyramid of Giza was built over 20 years using 2.3 million limestone blocks, each weighing about 2.5 tons...</div>
                  </div>
                  <div className="reel-progress"><div className="reel-progress-fill" style={{ width: '55%' }} /></div>
                </div>
                <div className="ph-bottom-nav">
                  <div className="ph-nav-item active"><IcoHome /></div>
                  <div className="ph-nav-item"><IcoDoc /></div>
                  <div className="ph-nav-item"><IcoUpload /></div>
                  <div className="ph-nav-item"><IcoBookmark /></div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ═══ PROBLEM ═══ */}
      <section className="problem" id="problem">
        <div className="problem-inner reveal">
          <div>
            <div className="section-label">The Problem</div>
            <h2 className="section-title">Documents are stuck in the past. Your brain isn&rsquo;t.</h2>
            <p className="section-desc">We share knowledge through PDFs and documents — but nobody actually reads them. People retain barely a fraction of what they passively read, yet the reading experience hasn&rsquo;t changed in decades.</p>
            <p className="section-desc" style={{ marginTop: '0.8rem' }}>Meanwhile, short-form content has rewired how we consume information. Verso bridges this gap.</p>
          </div>
          <div className="stat-grid">
            <div className="stat-card"><div className="stat-number">~15%</div><div className="stat-label">Average retention from passive reading</div></div>
            <div className="stat-card"><div className="stat-number">73%</div><div className="stat-label">Prefer short-form content for learning</div></div>
            <div className="stat-card"><div className="stat-number">0</div><div className="stat-label">Tools that make documents feel like scrolling a feed</div></div>
            <div className="stat-card"><div className="stat-number">100%</div><div className="stat-label">Of your data stays on your device</div></div>
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="how-it-works" id="how">
        <div className="section-label reveal">How It Works</div>
        <h2 className="section-title reveal" style={{ textAlign: 'center' }}>From PDF to feed in seconds</h2>
        <p className="section-desc reveal" style={{ textAlign: 'center' }}>Four steps. Zero cloud. All intelligence, all local.</p>
        <div className="steps-container reveal">
          <div className="step-card">
            <div className="step-icon upload">{'\uD83D\uDCC4'}</div>
            <div className="step-number">01</div>
            <div className="step-title">Upload</div>
            <div className="step-desc">Drop any PDF or DOCX. Verso auto-detects the document type and starts processing immediately.</div>
          </div>
          <div className="step-connector">&rarr;</div>
          <div className="step-card">
            <div className="step-icon process">{'\u26A1'}</div>
            <div className="step-number">02</div>
            <div className="step-title">AI Processes</div>
            <div className="step-desc">Local AI breaks your document into topics, generates summaries, flashcards, and audio — progressively.</div>
          </div>
          <div className="step-connector">&rarr;</div>
          <div className="step-card">
            <div className="step-icon learn">{'\uD83D\uDCF1'}</div>
            <div className="step-number">03</div>
            <div className="step-title">Swipe &amp; Learn</div>
            <div className="step-desc">Scroll through your personalized reel feed. Each reel is a bite-sized learning moment with audio.</div>
          </div>
          <div className="step-connector">&rarr;</div>
          <div className="step-card">
            <div className="step-icon chat">{'\uD83D\uDCAC'}</div>
            <div className="step-number">04</div>
            <div className="step-title">Chat &amp; Recall</div>
            <div className="step-desc">Ask questions about your document. Flip flashcards for active recall. Everything grounded in your content.</div>
          </div>
        </div>
      </section>

      {/* ═══ FEATURES ═══ */}
      <section className="features" id="features">
        <div className="section-label reveal">Features</div>
        <h2 className="section-title reveal" style={{ textAlign: 'center' }}>Everything you need to learn from any document</h2>
        <div className="features-grid reveal">
          <div className="feature-card highlight">
            <span className="feature-emoji">{'\uD83C\uDFAC'}</span>
            <div className="feature-name">Swipeable Reel Feed</div>
            <div className="feature-desc">Full-screen vertical swipe experience — just like Instagram or TikTok. Each reel is a structured learning moment with title, summary, category badge, keywords, and page reference. Auto-play audio. Infinite scroll.</div>
            <span className="feature-tag">Core Experience</span>
          </div>
          <div className="feature-card">
            <span className="feature-emoji">{'\uD83E\uDDE0'}</span>
            <div className="feature-name">Smart Algorithm</div>
            <div className="feature-desc">No quizzes. Verso watches what you scroll, skip, bookmark, and listen to — then adapts your content.</div>
          </div>
          <div className="feature-card">
            <span className="feature-emoji">{'\uD83C\uDFB4'}</span>
            <div className="feature-name">Auto Flashcards</div>
            <div className="feature-desc">Every reel generates question/answer flashcards for active recall and self-testing from a dedicated tab.</div>
          </div>
          <div className="feature-card">
            <span className="feature-emoji">{'\uD83D\uDCAC'}</span>
            <div className="feature-name">RAG Chat Q&amp;A</div>
            <div className="feature-desc">Ask anything about your document. Get grounded answers with source citations and page references. All local.</div>
          </div>
          <div className="feature-card highlight">
            <span className="feature-emoji">{'\uD83C\uDFA7'}</span>
            <div className="feature-name">Audio Narration</div>
            <div className="feature-desc">Every reel comes with neural text-to-speech narration. Hit play and learn while commuting, cooking, or working out. Generated locally, cached for instant replay.</div>
            <span className="feature-tag">Hands-free Learning</span>
          </div>
          <div className="feature-card">
            <span className="feature-emoji">{'\uD83D\uDCCB'}</span>
            <div className="feature-name">Progressive Processing</div>
            <div className="feature-desc">Reels appear within seconds of upload — you start learning before the document is fully processed.</div>
          </div>
          <div className="feature-card">
            <span className="feature-emoji">{'\uD83D\uDD16'}</span>
            <div className="feature-name">Bookmarks &amp; Progress</div>
            <div className="feature-desc">Save any reel or flashcard. Track your reading progress across all uploads.</div>
          </div>
          <div className="feature-card">
            <span className="feature-emoji">{'\uD83D\uDCE5'}</span>
            <div className="feature-name">Download &amp; Save</div>
            <div className="feature-desc">Export reels, flashcards, and audio as bundled packages for truly offline use anywhere.</div>
          </div>
        </div>
      </section>

      {/* ═══ LOCAL AI ═══ */}
      <section className="local-ai" id="local">
        <div className="local-ai-card reveal">
          <span className="local-ai-icon">{'\uD83D\uDEE1\uFE0F'}</span>
          <h2>Runs <em>entirely</em> on your machine</h2>
          <p>Verso is built local-first. No cloud APIs. No data uploads. No internet required. Your confidential documents — medical records, legal contracts, proprietary research — never leave your device.</p>
          <div className="local-pills">
            <div className="local-pill"><span>{'\u2705'}</span> Zero cloud dependency</div>
            <div className="local-pill"><span>{'\uD83D\uDD12'}</span> Complete data privacy</div>
            <div className="local-pill"><span>{'\u2708\uFE0F'}</span> Works offline</div>
            <div className="local-pill"><span>{'\uD83D\uDCBB'}</span> Runs on 8GB RAM</div>
            <div className="local-pill"><span>{'\u26A1'}</span> Local LLM powered</div>
          </div>
        </div>
      </section>

      {/* ═══ ALGORITHM ═══ */}
      <section className="algorithm" id="algo">
        <div className="algorithm-inner reveal">
          <div>
            <div className="section-label">The Algorithm</div>
            <h2 className="section-title">We don&rsquo;t ask what you like. We learn from what you do.</h2>
            <p className="section-desc">New users land on a feed of 100 pre-loaded reels across 10 subjects. As you scroll, skip, bookmark, and listen — Verso&rsquo;s algorithm learns your preferences in real-time.</p>
            <p className="section-desc" style={{ marginTop: '0.6rem', fontStyle: 'italic', color: 'var(--accent-cyan)', fontSize: '0.9rem' }}>No onboarding quiz. Just scroll.</p>
          </div>
          <div className="algo-visual">
            <div className="algo-step"><div className="algo-step-num">1</div><div className="algo-step-text"><strong>You scroll reels</strong> — science, history, business, medicine, tech...</div></div>
            <div className="algo-step"><div className="algo-step-num">2</div><div className="algo-step-text"><strong>We track signals</strong> — watch time, skips, bookmarks, audio plays</div></div>
            <div className="algo-step"><div className="algo-step-num">3</div><div className="algo-step-text"><strong>Preferences emerge</strong> — after ~10 interactions, we know your style</div></div>
            <div className="algo-step"><div className="algo-step-num">4</div><div className="algo-step-text"><strong>Your PDF reels adapt</strong> — generated to match how you actually learn</div></div>
            <div className="algo-step"><div className="algo-step-num">5</div><div className="algo-step-text"><strong>Feed evolves</strong> — platform + your reels, ranked by your behavior</div></div>
          </div>
        </div>
      </section>

      {/* ═══ TECH STACK ═══ */}
      <section className="tech-stack">
        <div className="section-label reveal">Built With</div>
        <h2 className="section-title reveal" style={{ textAlign: 'center' }}>Lean stack, maximum impact</h2>
        <p className="section-desc reveal" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>~3.0–3.3 GB peak RAM &bull; Fully local/offline &bull; No external API calls</p>
        <div className="tech-grid reveal">
          {['FastAPI', 'Ollama', 'Qwen 2.5', 'ChromaDB', 'ffmpeg', 'Edge-TTS / Piper', 'PyMuPDF', 'python-docx', 'nomic-embed-text', 'React (Vite)', 'Zustand', 'Swiper.js', 'Tailwind CSS v4', 'Axios', 'WebSocket'].map((t) => (
            <div key={t} className="tech-chip">{t}</div>
          ))}
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="landing-footer">
        <div className="logo">
          <div className="logo-icon"><VersoLogo id="vg4" size={24} /></div>
          <div className="logo-text">Verso <span>AI</span></div>
        </div>
        <p>Built for the Local AI Hackathon 2026 — 100% offline, 100% private</p>
        <div className="footer-links">
          <a href="#">GitHub</a>
          <a href="#">Docs</a>
          <a href="#">Demo</a>
        </div>
      </footer>

    </div>
  )
}
