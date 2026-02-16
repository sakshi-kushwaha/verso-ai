export default function Input({ label, type = 'text', value, onChange, placeholder, iconL, iconR, onIconR }) {
  return (
    <div className="mb-4">
      {label && <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wide mb-1.5">{label}</label>}
      <div className="flex items-center gap-2.5 bg-surface-alt border border-border rounded-lg px-3.5">
        {iconL && <span className="text-text-muted flex shrink-0">{iconL}</span>}
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className="flex-1 bg-transparent border-none outline-none text-text text-sm py-3 placeholder:text-text-muted/50"
        />
        {iconR && <span onClick={onIconR} className="text-text-muted cursor-pointer flex shrink-0">{iconR}</span>}
      </div>
    </div>
  )
}
