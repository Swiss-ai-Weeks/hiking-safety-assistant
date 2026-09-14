import type { ReactNode } from 'react'
import { Link, type To } from 'react-router'
import { useT } from '../i18n'
import { ChevronLeft } from './icons'

interface Props {
  title: ReactNode
  subtitle?: ReactNode
  backTo: To
  action?: ReactNode
  bordered?: boolean
}

export function ScreenHeader({ title, subtitle, backTo, action, bordered = true }: Props) {
  const { t } = useT()
  return (
    <header
      className={`sticky top-0 z-20 flex items-center gap-2 bg-canvas/95 px-3.5 pt-[max(env(safe-area-inset-top),12px)] pb-2.5 backdrop-blur-sm ${
        bordered ? 'border-b border-rule' : ''
      }`}
    >
      <Link
        to={backTo}
        aria-label={t('common.back')}
        className="flex size-10 shrink-0 items-center justify-center rounded-full text-plum hover:bg-subtle"
      >
        <ChevronLeft />
      </Link>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[15px] font-semibold">{title}</h1>
        {subtitle && <p className="truncate text-xs text-muted">{subtitle}</p>}
      </div>
      {action}
    </header>
  )
}
