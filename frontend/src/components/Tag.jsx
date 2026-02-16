export default function Tag({ children, color, className = '' }) {
  const style = color
    ? { color, backgroundColor: `${color}15` }
    : undefined;

  return (
    <span
      className={`inline-flex px-2.5 py-1 rounded-md text-[10.5px] font-bold uppercase tracking-wide ${
        color ? '' : 'text-primary-light bg-primary/10'
      } ${className}`}
      style={style}
    >
      {children}
    </span>
  )
}
