import { useEffect } from 'react'
import { Outlet, ScrollRestoration, useLocation, useSearchParams } from 'react-router'
import { usePlan } from '../store/plan'
import { LoadBoundary } from './LoadBoundary'

/** Phone-width column: full width on phones, centred on the page canvas on desktop. */
export function AppShell() {
  const { pathname } = useLocation()
  const [params, setParams] = useSearchParams()
  const lang = usePlan((s) => s.lang)
  const setRouteId = usePlan((s) => s.setRouteId)
  const dark = pathname.startsWith('/field')

  // `?routeId=` opens a route the backend has computed. Until the picker lands in Phase 4 this is
  // how a real routed hike is reached; it stays useful afterwards as a way to share one.
  const requestedRouteId = params.get('routeId')
  useEffect(() => {
    if (!requestedRouteId) return
    setRouteId(requestedRouteId)
    // Consumed, not kept: leaving it in the URL would re-apply it on every later navigation and
    // quietly override whatever the hiker picked next.
    setParams(
      (current) => {
        current.delete('routeId')
        return current
      },
      { replace: true },
    )
  }, [requestedRouteId, setRouteId, setParams])

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
        <LoadBoundary resetKey={pathname}>
          <Outlet />
        </LoadBoundary>
      </div>
      <ScrollRestoration />
    </div>
  )
}
