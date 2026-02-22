export default function PasswordStrength({ password }) {
  if (!password) return null

  const checks = [
    { label: '8+ characters', ok: password.length >= 8 },
    { label: 'Uppercase letter', ok: /[A-Z]/.test(password) },
    { label: 'Lowercase letter', ok: /[a-z]/.test(password) },
    { label: 'Number', ok: /\d/.test(password) },
  ]
  const passed = checks.filter((c) => c.ok).length
  const level = passed <= 1 ? 'weak' : passed <= 2 ? 'fair' : passed <= 3 ? 'good' : 'strong'
  const colors = { weak: '#ef4444', fair: '#f59e0b', good: '#3b82f6', strong: '#22c55e' }
  const labels = { weak: 'Weak', fair: 'Fair', good: 'Good', strong: 'Strong' }

  return (
    <div className="pw-strength">
      <div className="pw-strength-bar">
        <div
          className="pw-strength-fill"
          style={{
            width: `${(passed / 4) * 100}%`,
            background: colors[level],
          }}
        />
      </div>
      <div className="pw-strength-meta">
        <span style={{ color: colors[level], fontWeight: 600 }}>{labels[level]}</span>
      </div>
      <div className="pw-strength-checks">
        {checks.map((c) => (
          <span key={c.label} className={`pw-check ${c.ok ? 'ok' : ''}`}>
            {c.ok ? '\u2713' : '\u2717'} {c.label}
          </span>
        ))}
      </div>
    </div>
  )
}
