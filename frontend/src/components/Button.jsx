const variants = {
  primary: 'bg-primary text-white shadow-lg shadow-primary/25 hover:bg-primary-dark',
  secondary: 'bg-surface-alt text-text border border-border hover:bg-surface',
  ghost: 'bg-transparent text-text-muted py-2 px-3.5 hover:text-text',
  success: 'bg-success text-white hover:opacity-90',
  warning: 'bg-warning text-white hover:opacity-90',
  error: 'bg-danger text-white hover:opacity-90',
  danger: 'bg-danger/10 text-danger hover:bg-danger/20',
}

export default function Button({ children, variant = 'primary', onClick, disabled, full, className = '' }) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      className={`inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold
        transition-all duration-200 ease-out outline-none border-none
        ${full ? 'w-full' : ''} ${disabled ? 'opacity-45 cursor-not-allowed' : 'cursor-pointer hover:-translate-y-0.5'}
        ${variants[variant] || variants.primary} ${className}`}
    >
      {children}
    </button>
  )
}
