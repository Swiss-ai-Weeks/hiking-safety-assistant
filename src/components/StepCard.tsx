import type { ReactNode } from 'react'

interface Props {
  step: number
  done: boolean
  title: string
  dimmed?: boolean
  children?: ReactNode
}

/** Numbered pre-flight step. A plum check replaces the number once done. */
export function StepCard({ step, done, title, dimmed = false, children }: Props) {
  return (
    <section
      className={`flex flex-col gap-3 rounded-card border border-line bg-card p-4 transition-opacity ${dimmed ? 'opacity-55' : ''}`}
    >
      <div className="flex items-start gap-2.5">
        <span
          aria-hidden="true"
          className={`flex size-6 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold text-white ${
            done ? 'bg-plum' : 'bg-ink'
          }`}
        >
          {done ? '✓' : step}
        </span>
        <h2 className="text-base leading-[1.35] font-semibold">{title}</h2>
      </div>
      {children}
    </section>
  )
}
