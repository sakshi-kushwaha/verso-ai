import { useState, useEffect } from 'react'

export default function SplashScreen({ onFinish }) {
  const [fadeOut, setFadeOut] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setFadeOut(true), 2200)
    const t2 = setTimeout(onFinish, 2800)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [onFinish])

  const logoFace = (
    <svg width="48" height="48" viewBox="0 0 28 28" fill="none">
      <rect x="1" y="3" width="10" height="22" rx="3" fill="#6366F1" />
      <rect x="14" y="7" width="10" height="14" rx="3" fill="#818CF8" opacity="0.6" />
      <rect x="8" y="10" width="10" height="8" rx="2" fill="#6366F1" opacity="0.35" />
    </svg>
  )

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

      <div className="relative flex flex-col items-center gap-6 fade-up">
        {/* 3D Rotating Cube */}
        <div className="splash-scene">
          <div className="splash-cube">
            <div className="splash-face splash-front">{logoFace}</div>
            <div className="splash-face splash-back">{logoFace}</div>
            <div className="splash-face splash-right">{logoFace}</div>
            <div className="splash-face splash-left">{logoFace}</div>
            <div className="splash-face splash-top">{logoFace}</div>
            <div className="splash-face splash-bottom">{logoFace}</div>
          </div>
        </div>

        {/* Text */}
        <h1 className="text-4xl md:text-5xl font-bold font-display tracking-tight">
          Verso <span className="text-primary">AI</span>
        </h1>

      </div>

      <style>{`
        .splash-scene {
          width: 100px;
          height: 100px;
          perspective: 400px;
        }
        .splash-cube {
          width: 100%;
          height: 100%;
          position: relative;
          transform-style: preserve-3d;
          animation: splash-spin 4s linear infinite;
        }
        .splash-face {
          position: absolute;
          width: 100px;
          height: 100px;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px solid rgba(99, 102, 241, 0.15);
          border-radius: 16px;
          background: rgba(21, 27, 59, 0.85);
          backdrop-filter: blur(8px);
          box-shadow: 0 0 30px rgba(99, 102, 241, 0.1), inset 0 0 20px rgba(99, 102, 241, 0.05);
        }
        .splash-front  { transform: rotateY(0deg)   translateZ(50px); }
        .splash-back   { transform: rotateY(180deg)  translateZ(50px); }
        .splash-right  { transform: rotateY(90deg)   translateZ(50px); }
        .splash-left   { transform: rotateY(-90deg)  translateZ(50px); }
        .splash-top    { transform: rotateX(90deg)   translateZ(50px); }
        .splash-bottom { transform: rotateX(-90deg)  translateZ(50px); }

        @keyframes splash-spin {
          0%   { transform: rotateX(-20deg) rotateY(0deg); }
          100% { transform: rotateX(-20deg) rotateY(360deg); }
        }
      `}</style>
    </div>
  )
}
