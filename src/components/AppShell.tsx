import { useEffect } from 'react'
import { Outlet, ScrollRestoration, useLocation } from 'react-router'
import { usePlan } from '../store/plan'

/** Phone-width column: full width on phones, centred on the page canvas on desktop. */
export function AppShell() {
  const { pathname } = useLocation()
  const lang = usePlan((s) => s.lang)
  const dark = pathname.startsWith('/field')

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  useEffect(() => {
    document.body.style.backgroundColor = dark ? 'var(--color-field)' : ''
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#1a1714' : '#f7f4ef')
  }, [dark])

  return (
    <div className={dark ? 'bg-field' : 'bg-page'}>
      <div
        className={`mx-auto flex min-h-dvh w-full max-w-[430px] flex-col min-[431px]:shadow-[0_0_0_1px_var(--color-rule)] ${
          dark ? 'bg-field text-white' : 'bg-canvas text-ink'
        }`}
      >
        <Outlet />
      </div>
      <ScrollRestoration />
    </div>
  )
}
