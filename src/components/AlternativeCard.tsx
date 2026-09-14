import type { ReactNode } from 'react'

interface Props {
  title: string
  body: string
  badge?: ReactNode
  suggested?: boolean
  onSelect?: () => void
}

export function AlternativeCard({ title, body, badge, suggested = false, onSelect }: Props) {
  const className = `flex w-full flex-col gap-1.5 rounded-card bg-card p-4 text-left ${
    suggested ? 'border-[1.5px] border-plum' : 'border border-line'
  } ${onSelect ? 'transition-colors hover:bg-subtle' : ''}`

  const content = (
    <>
      <span className="flex items-center justify-between gap-3">
        <span className="text-base font-semibold">{title}</span>
        {badge}
      </span>
      <span className="text-sm leading-normal text-ink-2">{body}</span>
    </>
  )

  return onSelect ? (
    <button type="button" onClick={onSelect} className={className}>
      {content}
    </button>
  ) : (
    <div className={className}>{content}</div>
  )
}
