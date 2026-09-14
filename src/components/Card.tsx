import type { HTMLAttributes, ReactNode } from 'react'

export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-card border border-line bg-card ${className}`} {...rest} />
}

export function Eyebrow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`text-xs font-semibold tracking-[0.08em] text-muted uppercase ${className}`}>{children}</p>
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="px-1 pt-1 text-[15px] font-semibold">{children}</h2>
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-card bg-subtle ${className}`} />
}

export function Disclaimer({ children }: { children: ReactNode }) {
  return <p className="px-1 pt-1.5 text-xs leading-normal text-muted">{children}</p>
}
