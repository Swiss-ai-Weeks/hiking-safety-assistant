import type { ReactNode } from 'react'

/** Bottom-anchored action area. One primary action per screen. */
export function BottomAction({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  return (
    <div
      className={`sticky bottom-0 z-20 mt-auto flex gap-2.5 px-[22px] pt-4 pb-[max(env(safe-area-inset-bottom),28px)] ${
        dark ? 'bg-field' : 'bg-linear-to-t from-canvas from-75% to-canvas/0'
      }`}
    >
      {children}
    </div>
  )
}
