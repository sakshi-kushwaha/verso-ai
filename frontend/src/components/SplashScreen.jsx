import { useState, useEffect } from 'react'

export default function SplashScreen({ onFinish }) {
  const [fadeOut, setFadeOut] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setFadeOut(true), 2800)
    const t2 = setTimeout(onFinish, 3400)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [onFinish])

  return (
    <div
      className={`fixed inset-0 z-50 bg-bg flex flex-col items-center justify-center transition-opacity duration-700 ${
        fadeOut ? 'opacity-0' : 'opacity-100'
      }`}
    >
      {/* Background glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-primary/10 rounded-full blur-[120px]" />
      </div>

      <div className="relative flex flex-col items-center gap-8 fade-up">
        {/* 3D Flipping Book */}
        <div className="book-scene">
          <div className="book">
            {/* Spine (left edge) */}
            <div className="book-spine" />
            {/* Back cover */}
            <div className="book-cover book-back">
              <div className="book-inner-line" />
              <div className="book-inner-line short" />
            </div>
            {/* Middle pages */}
            <div className="book-page page-3">
              <div className="page-line" style={{ width: '70%', top: '25%' }} />
              <div className="page-line" style={{ width: '55%', top: '38%' }} />
              <div className="page-line" style={{ width: '65%', top: '51%' }} />
              <div className="page-line" style={{ width: '40%', top: '64%' }} />
            </div>
            <div className="book-page page-2">
              <div className="page-line" style={{ width: '60%', top: '25%' }} />
              <div className="page-line" style={{ width: '75%', top: '38%' }} />
              <div className="page-line" style={{ width: '50%', top: '51%' }} />
              <div className="page-line" style={{ width: '65%', top: '64%' }} />
              <div className="page-line" style={{ width: '45%', top: '77%' }} />
            </div>
            <div className="book-page page-1">
              <div className="page-line" style={{ width: '55%', top: '25%' }} />
              <div className="page-line" style={{ width: '70%', top: '38%' }} />
              <div className="page-line" style={{ width: '60%', top: '51%' }} />
            </div>
            {/* Front cover */}
            <div className="book-cover book-front">
              <svg width="36" height="36" viewBox="0 0 28 28" fill="none">
                <rect x="1" y="3" width="10" height="22" rx="3" fill="#3B82F6" />
                <rect x="14" y="7" width="10" height="14" rx="3" fill="#60A5FA" opacity="0.6" />
                <rect x="8" y="10" width="10" height="8" rx="2" fill="#3B82F6" opacity="0.35" />
              </svg>
              <div className="book-cover-title">Verso</div>
            </div>
          </div>
        </div>

        {/* Text */}
        <h1 className="text-4xl md:text-5xl font-bold font-display tracking-tight">
          Verso <span className="text-primary">AI</span>
        </h1>
      </div>

      <style>{`
        .book-scene {
          width: 120px;
          height: 150px;
          perspective: 800px;
        }
        .book {
          width: 100%;
          height: 100%;
          position: relative;
          transform-style: preserve-3d;
          animation: bookFloat 3s ease-in-out infinite;
        }

        /* --- Spine --- */
        .book-spine {
          position: absolute;
          left: 0; top: 0;
          width: 16px;
          height: 100%;
          background: linear-gradient(180deg, #2563EB, #1D4ED8);
          transform: rotateY(-90deg) translateZ(0px);
          transform-origin: left center;
          border-radius: 3px 0 0 3px;
          box-shadow: inset -2px 0 6px rgba(0,0,0,0.3);
        }

        /* --- Covers --- */
        .book-cover {
          position: absolute;
          width: 120px;
          height: 150px;
          border-radius: 2px 10px 10px 2px;
          backface-visibility: hidden;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          transform-origin: left center;
        }
        .book-front {
          background: linear-gradient(135deg, #1E293B 0%, #111827 100%);
          border: 1px solid rgba(59,130,246,0.2);
          box-shadow:
            0 10px 40px rgba(0,0,0,0.4),
            0 0 20px rgba(59,130,246,0.1),
            inset 0 1px 0 rgba(255,255,255,0.05);
          transform: rotateY(0deg) translateZ(8px);
          z-index: 5;
          animation: bookOpen 4s ease-in-out infinite;
        }
        .book-cover-title {
          font-family: "Outfit", sans-serif;
          font-size: 0.75rem;
          font-weight: 700;
          color: rgba(59,130,246,0.7);
          margin-top: 8px;
          letter-spacing: 2px;
          text-transform: uppercase;
        }
        .book-back {
          background: linear-gradient(135deg, #1E293B, #0F172A);
          border: 1px solid rgba(59,130,246,0.1);
          transform: rotateY(0deg) translateZ(-8px);
          box-shadow: 0 10px 30px rgba(0,0,0,0.5);
          padding: 30px 20px;
          align-items: flex-start;
          gap: 8px;
        }
        .book-inner-line {
          width: 70%;
          height: 2px;
          background: rgba(59,130,246,0.08);
          border-radius: 1px;
        }
        .book-inner-line.short { width: 45%; }

        /* --- Pages --- */
        .book-page {
          position: absolute;
          width: 116px;
          height: 146px;
          top: 2px;
          left: 2px;
          background: linear-gradient(135deg, #1a2236, #151d30);
          border-radius: 1px 8px 8px 1px;
          transform-origin: left center;
          border: 1px solid rgba(59,130,246,0.06);
        }
        .page-line {
          position: absolute;
          left: 15%;
          height: 2px;
          background: rgba(96,165,250,0.08);
          border-radius: 1px;
        }
        .page-1 {
          transform: translateZ(5px);
          z-index: 4;
          animation: pageFlip1 4s ease-in-out infinite;
        }
        .page-2 {
          transform: translateZ(2px);
          z-index: 3;
          animation: pageFlip2 4s ease-in-out infinite;
        }
        .page-3 {
          transform: translateZ(-1px);
          z-index: 2;
          animation: pageFlip3 4s ease-in-out infinite;
        }

        /* --- Animations --- */
        @keyframes bookFloat {
          0%, 100% { transform: rotateX(5deg) rotateY(-20deg) translateY(0px); }
          50%      { transform: rotateX(5deg) rotateY(-20deg) translateY(-8px); }
        }

        @keyframes bookOpen {
          0%, 15%  { transform: rotateY(0deg)   translateZ(8px); }
          35%, 65% { transform: rotateY(-140deg) translateZ(8px); }
          85%, 100%{ transform: rotateY(0deg)   translateZ(8px); }
        }

        @keyframes pageFlip1 {
          0%, 20%  { transform: rotateY(0deg)   translateZ(5px); }
          40%, 60% { transform: rotateY(-130deg) translateZ(5px); }
          80%, 100%{ transform: rotateY(0deg)   translateZ(5px); }
        }
        @keyframes pageFlip2 {
          0%, 25%  { transform: rotateY(0deg)   translateZ(2px); }
          45%, 55% { transform: rotateY(-120deg) translateZ(2px); }
          75%, 100%{ transform: rotateY(0deg)   translateZ(2px); }
        }
        @keyframes pageFlip3 {
          0%, 30%  { transform: rotateY(0deg)   translateZ(-1px); }
          50%      { transform: rotateY(-110deg) translateZ(-1px); }
          70%, 100%{ transform: rotateY(0deg)   translateZ(-1px); }
        }
      `}</style>
    </div>
  )
}
