export default function Tag({ children, className = '' }) {
  return (
    <span className={`inline-flex px-2.5 py-1 rounded-md text-[10.5px] font-bold uppercase tracking-wide text-primary-light bg-primary/10 ${className}`}>
      {children}
    </span>
  )
}
