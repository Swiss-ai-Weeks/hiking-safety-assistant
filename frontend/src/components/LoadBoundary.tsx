import { QueryErrorResetBoundary } from '@tanstack/react-query'
import { Component, Suspense, type ReactNode } from 'react'
import { useT } from '../i18n'
import { Button } from './Button'
import { Skeleton } from './Card'

interface ErrorBoundaryProps {
  /** A change (e.g. navigating away) clears the error. */
  resetKey: string
  onReset: () => void
  children: ReactNode
}

class ErrorBoundary extends Component<ErrorBoundaryProps, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidUpdate(prev: ErrorBoundaryProps) {
    if (this.state.failed && prev.resetKey !== this.props.resetKey) this.reset()
  }

  reset = () => {
    this.props.onReset()
    this.setState({ failed: false })
  }

  render() {
    return this.state.failed ? <LoadError onRetry={this.reset} /> : this.props.children
  }
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  const { t } = useT()
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
