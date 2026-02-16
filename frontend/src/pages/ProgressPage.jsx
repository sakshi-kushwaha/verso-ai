export default function ProgressPage() {
  const stats = {
    reelsViewed: 3,
    reelsTotal: 5,
    flashcardsDone: 2,
    flashcardsTotal: 5,
    chatQuestions: 4,
    chatTotal: 10,
    streak: 1,
  }

  const overall = Math.round(
    ((stats.reelsViewed / stats.reelsTotal +
      stats.flashcardsDone / stats.flashcardsTotal +
      stats.chatQuestions / stats.chatTotal) /
      3) *
      100
  )

  const circumference = 2 * Math.PI * 42
  const strokeDash = (overall / 100) * circumference

  return (
    <div className="max-w-xl mx-auto p-6 pt-10 fade-up">
      <h1 className="text-2xl font-bold font-display mb-1">Progress</h1>
      <p className="text-text-muted text-sm mb-8">Track your learning journey</p>

      {/* Hero donut card */}
      <div className="bg-surface rounded-2xl p-8 border border-border flex flex-col items-center mb-6">
        <div className="relative w-40 h-40 mb-4">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(99,102,241,0.1)" strokeWidth="8" />
            <circle
              cx="50" cy="50" r="42" fill="none"
              stroke="url(#donutGrad)" strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${strokeDash} ${circumference}`}
              className="transition-all duration-1000"
            />
            <defs>
              <linearGradient id="donutGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#6366F1" />
                <stop offset="100%" stopColor="#818CF8" />
              </linearGradient>
            </defs>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl font-bold font-display">{overall}%</span>
            <span className="text-text-muted text-xs">Complete</span>
          </div>
        </div>
        <p className="text-text-secondary text-sm">Deep Learning Fundamentals.pdf</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Reels Viewed', done: stats.reelsViewed, total: stats.reelsTotal, color: '#6366F1' },
          { label: 'Flashcards', done: stats.flashcardsDone, total: stats.flashcardsTotal, color: '#8B5CF6' },
          { label: 'Chat Questions', done: stats.chatQuestions, total: stats.chatTotal, color: '#EC4899' },
        ].map((stat, i) => (
          <div
            key={i}
            className="bg-surface rounded-xl p-5 border border-border fade-up"
            style={{ animationDelay: `${i * 0.1}s` }}
          >
            <p className="text-text-muted text-xs font-semibold uppercase tracking-wide mb-2">{stat.label}</p>
            <p className="text-2xl font-bold font-display mb-3">
              {stat.done} <span className="text-text-muted text-sm font-normal">/ {stat.total}</span>
            </p>
            <div className="h-1.5 rounded-full bg-surface-alt overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${(stat.done / stat.total) * 100}%`,
                  backgroundColor: stat.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Streak card */}
      <div className="bg-surface rounded-xl p-5 border border-border text-center">
        <span className="text-3xl">&#x1F525;</span>
        <p className="text-lg font-bold font-display mt-2">{stats.streak} Day Streak</p>
        <p className="text-text-muted text-sm">Keep it going! Consistency is key.</p>
      </div>
    </div>
  )
}
