import clsx from 'clsx'

interface EVBadgeProps {
  ev: number
  size?: 'sm' | 'md' | 'lg'
}

function getEvColor(ev: number) {
  if (ev >= 10) return 'bg-emerald-900/60 text-emerald-300 ring-1 ring-emerald-500'
  if (ev >= 5) return 'bg-green-900/60 text-green-300 ring-1 ring-green-500'
  if (ev >= 3) return 'bg-lime-900/60 text-lime-300 ring-1 ring-lime-600'
  if (ev >= 2) return 'bg-yellow-900/60 text-yellow-300 ring-1 ring-yellow-600'
  return 'bg-orange-900/60 text-orange-300 ring-1 ring-orange-600'
}

export default function EVBadge({ ev, size = 'md' }: EVBadgeProps) {
  const sizeClass = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'
  return (
    <span className={clsx('inline-flex items-center rounded font-mono font-bold', sizeClass, getEvColor(ev))}>
      +{ev.toFixed(2)}%
    </span>
  )
}
