import clsx from 'clsx'
import { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: LucideIcon
  iconColor?: string
  trend?: 'up' | 'down' | 'neutral'
  highlight?: boolean
}

export default function StatCard({
  title, value, subtitle, icon: Icon, iconColor = 'text-brand', trend, highlight
}: StatCardProps) {
  return (
    <div className={clsx(
      'card flex flex-col gap-3',
      highlight && 'ring-1 ring-brand/50 bg-brand/5'
    )}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</span>
        {Icon && <Icon size={16} className={iconColor} />}
      </div>
      <div>
        <div className={clsx(
          'text-2xl font-bold font-mono',
          trend === 'up' ? 'text-brand' : trend === 'down' ? 'text-red-400' : 'text-slate-100'
        )}>
          {value}
        </div>
        {subtitle && <div className="text-xs text-slate-500 mt-1">{subtitle}</div>}
      </div>
    </div>
  )
}
