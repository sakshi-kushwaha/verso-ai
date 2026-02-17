export function Spinner({ text = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 fade-up">
      <div className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-2.5 h-2.5 rounded-full bg-primary pulse-3"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
      {text && <p className="text-text-muted text-sm">{text}</p>}
    </div>
  )
}

export function EmptyState({ icon, title, subtitle, children }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6 fade-up">
      {icon && (
        <div className="w-16 h-16 rounded-2xl bg-surface-alt flex items-center justify-center text-text-muted mb-4">
          {icon}
        </div>
      )}
      {title && <p className="font-semibold font-display text-lg mb-1">{title}</p>}
      {subtitle && <p className="text-text-muted text-sm max-w-xs">{subtitle}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}

export function ErrorState({ message = 'Something went wrong', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6 fade-up">
      <div className="w-16 h-16 rounded-2xl bg-danger/10 flex items-center justify-center text-danger mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <p className="font-semibold font-display text-lg mb-1">{message}</p>
      <p className="text-text-muted text-sm mb-4">Please check your connection and try again</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-5 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:opacity-90 transition-opacity cursor-pointer"
        >
          Retry
        </button>
      )}
    </div>
  )
}
