import { QueryErrorResetBoundary } from '@tanstack/react-query'
import { Component, Suspense, type ReactNode } from 'react'
import { ApiError } from '../api/client'
import { useT } from '../i18n'
import { useNavigate } from 'react-router'
import { usePlan } from '../store/plan'
import { Button } from './Button'
import { Skeleton } from './Card'

interface ErrorBoundaryProps {
  /** A change (e.g. navigating away) clears the error. */
  resetKey: string
  onReset: () => void
  children: ReactNode
}

class ErrorBoundary extends Component<ErrorBoundaryProps, { error: unknown }> {
  state: { error: unknown } = { error: null }

  static getDerivedStateFromError(error: unknown) {
    return { error }
  }

  componentDidUpdate(prev: ErrorBoundaryProps) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.reset()
  }

  reset = () => {
    this.props.onReset()
    this.setState({ error: null })
  }

  render() {
    return this.state.error ? <LoadError error={this.state.error} onRetry={this.reset} /> : this.props.children
  }
}

function LoadError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { t } = useT()
  const navigate = useNavigate()
  const setRouteId = usePlan((s) => s.setRouteId)

  // A 404 means the route itself is gone — a computed route that has aged out of the backend's
  // cache. Retrying can only 404 again, so the way out is searching for it again.
  if (error instanceof ApiError && error.status === 404) {
    return (
      <main role="alert" className="flex flex-1 flex-col justify-center gap-4 px-[22px] py-10">
        <p className="text-[15px] leading-normal">{t('common.routeGone')}</p>
        <Button
          variant="accent"
          size="md"
          onClick={() => {
            setRouteId(null)
            navigate('/routes/new')
            onRetry()
          }}
        >
          {t('common.routeGoneAction')}
        </Button>
      </main>
    )
  }

  return (
    <main role="alert" className="flex flex-1 flex-col justify-center gap-4 px-[22px] py-10">
      <p className="text-[15px] leading-normal">{t('common.loadError')}</p>
      <Button variant="accent" size="md" onClick={onRetry}>
        {t('common.retry')}
      </Button>
    </main>
  )
}

/** Loading and error states for screens that read from the backend. */
export function LoadBoundary({ resetKey, children }: { resetKey: string; children: ReactNode }) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ErrorBoundary resetKey={resetKey} onReset={reset}>
          <Suspense
            fallback={
              <div aria-busy="true" className="flex flex-1 flex-col gap-3.5 px-[18px] pt-[max(env(safe-area-inset-top),40px)]">
                <Skeleton className="h-24" />
                <Skeleton className="h-40" />
                <Skeleton className="h-28" />
              </div>
            }
          >
            {children}
          </Suspense>
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  )
}
