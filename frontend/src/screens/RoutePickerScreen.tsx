import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { createRoute, placeSearchQuery, routeQuery } from '../api/queries'
import { BottomAction } from '../components/BottomAction'
import { Button } from '../components/Button'
import { Card, SectionTitle } from '../components/Card'
import { SettingsIcon } from '../components/icons'
import { ScreenHeader } from '../components/ScreenHeader'
import type { PlaceRef } from '../domain/types'
import { useT, type MessageKey } from '../i18n'
import { usePlan } from '../store/plan'

const SEARCH_DEBOUNCE_MS = 300

/**
 * Routes to start from, one hard and one easy. Each end is spelled exactly as place search returns
 * it, so a suggestion builds the same route (and route id) as picking those places by hand.
 */
const SUGGESTED_ROUTES: { name: string; blurb: MessageKey; from: PlaceRef; to: PlaceRef }[] = [
  {
    name: 'Oeschinensee → Blüemlisalphütte',
    blurb: 'picker.suggest.hohturli',
    from: { name: 'See Oeschinensee (BE) - Kandersteg', latLng: [46.49836, 7.72667] },
    to: { name: 'Gebaeude Blüemlisalphütte SAC (BE) - Kandersteg', latLng: [46.51019, 7.77162] },
  },
  {
    name: 'Kleine Scheidegg → Männlichen',
    blurb: 'picker.suggest.mannlichen',
    from: { name: 'Ort Kleine Scheidegg (BE) - Lauterbrunnen', latLng: [46.58469, 7.96068] },
    to: { name: 'Männlichen (BE) - Lauterbrunnen,Grindelwald', latLng: [46.61206, 7.94194] },
  },
]

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

/** Why a route could not be built, in words the hiker can act on. */
function routeErrorKey(error: unknown): MessageKey {
  if (error instanceof ApiError && error.status === 503) {
    // The trail graph answers for itself: no path, or a point too far from any marked trail.
    if (error.source === 'swisstlm3d') return 'picker.noTrail'
  }
  return 'picker.unavailable'
}

/** One end of the route: a search box until a place is picked, then the place. */
function PlaceField({
  label,
  value,
  onChange,
  onRemove,
}: {
  label: string
  value: PlaceRef | null
  onChange: (place: PlaceRef | null) => void
  onRemove?: () => void
}) {
  const { t } = useT()
  const inputId = useId()
  const [text, setText] = useState('')
  const query = useDebounced(text, SEARCH_DEBOUNCE_MS)
  const search = useQuery({ ...placeSearchQuery(query), enabled: value === null && query.trim().length > 1 })

  if (value) {
    return (
      <div className="flex items-center justify-between gap-3 border-b border-divider px-4 py-3.5 last:border-0">
        <span className="flex min-w-0 flex-col gap-[3px]">
          <span className="text-xs text-muted">{label}</span>
          <span className="truncate text-[17px] font-medium">{value.name}</span>
        </span>
        <button
          type="button"
          onClick={() => {
            setText('')
            onChange(null)
          }}
          className="shrink-0 text-[13px] font-semibold text-plum"
        >
          {t('picker.change')}
        </button>
      </div>
    )
  }

  const results = search.data ?? []
  return (
    <div className="flex flex-col gap-1.5 border-b border-divider px-4 py-3.5 last:border-0">
      <span className="flex items-center justify-between">
        <label htmlFor={inputId} className="text-xs text-muted">
          {label}
        </label>
        {onRemove && (
          <button type="button" onClick={onRemove} className="text-[13px] font-semibold text-plum">
            {t('picker.removeVia')}
          </button>
        )}
      </span>
      <input
        id={inputId}
        type="search"
        autoComplete="off"
        value={text}
        placeholder={t('picker.placeholder')}
        onChange={(event) => setText(event.target.value)}
        className="w-full bg-transparent text-[17px] font-medium outline-none placeholder:font-normal placeholder:text-faint"
      />
      {query.trim().length > 1 && (
        <div role="status" aria-live="polite" className="text-[13px] text-muted">
          {search.isFetching && results.length === 0
            ? t('picker.searching')
            : search.isError
              ? t('picker.searchFailed')
              : search.isSuccess && results.length === 0
                ? t('picker.noResults', { query })
                : null}
        </div>
      )}
      {results.length > 0 && (
        <ul className="-mx-2 flex flex-col">
          {results.map((place) => (
            <li key={`${place.name}-${place.latLng.join()}`}>
              <button
                type="button"
                onClick={() => onChange({ name: place.name, latLng: place.latLng })}
                className="w-full rounded-control px-2 py-2 text-left text-[15px] hover:bg-subtle"
              >
                {place.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Pick two places (and optionally one on the way); the backend routes them over the official network. */
export function RoutePickerScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const openRoute = usePlan((s) => s.openRoute)
  // With nothing planned yet this is the first screen: no way back, and Settings is reached from here.
  const firstScreen = usePlan((s) => s.routeId === null)
  const [from, setFrom] = useState<PlaceRef | null>(null)
  const [to, setTo] = useState<PlaceRef | null>(null)
  const [via, setVia] = useState<PlaceRef | null>(null)
  const [viaOpen, setViaOpen] = useState(false)

  const build = useMutation({
    mutationFn: createRoute,
    onSuccess: (route) => {
      // The POST already returned the route; seed the cache so Plan renders without refetching.
      queryClient.setQueryData(routeQuery(route.id).queryKey, route)
      openRoute(route)
      navigate('/')
    },
  })

  const pickSuggestion = (suggestion: (typeof SUGGESTED_ROUTES)[number]) => {
    setFrom(suggestion.from)
    setTo(suggestion.to)
    setVia(null)
    setViaOpen(false)
  }

  const ready = from !== null && to !== null && (!viaOpen || via !== null)

  return (
    <>
      <ScreenHeader
        title={t('picker.title')}
        backTo={firstScreen ? undefined : '/'}
        action={
          firstScreen && (
            <Link
              to="/settings"
              aria-label={t('common.settings')}
              className="flex size-10 shrink-0 items-center justify-center rounded-full text-plum hover:bg-subtle"
            >
              <SettingsIcon />
            </Link>
          )
        }
      />
      <main className="flex flex-1 flex-col gap-3.5 px-[22px] pt-5 pb-2">
        <Card>
          <PlaceField label={t('picker.from')} value={from} onChange={setFrom} />
          {viaOpen && (
            <PlaceField
              label={t('picker.via')}
              value={via}
              onChange={setVia}
              onRemove={() => {
                setVia(null)
                setViaOpen(false)
              }}
            />
          )}
          <PlaceField label={t('picker.to')} value={to} onChange={setTo} />
        </Card>
        {!viaOpen && (
          <button type="button" onClick={() => setViaOpen(true)} className="self-start px-1 text-[13px] font-semibold text-plum">
            {t('picker.addVia')}
          </button>
        )}
        <p className="px-1 text-[13px] leading-normal text-muted">{t('picker.note')}</p>
        {build.isError && (
          <p role="alert" className="px-1 text-[13px] leading-normal text-sev-high">
            {t(routeErrorKey(build.error))}
          </p>
        )}
        <SectionTitle>{t('picker.suggested')}</SectionTitle>
        <ul className="flex flex-col gap-2.5">
          {SUGGESTED_ROUTES.map((suggestion) => (
            <li key={suggestion.name}>
              <button
                type="button"
                onClick={() => pickSuggestion(suggestion)}
                className="flex w-full flex-col gap-[3px] rounded-card border border-line bg-card px-4 py-3.5 text-left hover:bg-subtle"
              >
                <span className="text-[17px] font-medium">{suggestion.name}</span>
                <span className="text-[13px] text-muted">{t(suggestion.blurb)}</span>
              </button>
            </li>
          ))}
        </ul>
      </main>
      <BottomAction>
        <Button
          className="flex-1"
          disabled={!ready || build.isPending}
          onClick={() => from && to && build.mutate({ from, to, via: via ? [via] : [] })}
        >
          {build.isPending ? t('picker.building') : t('picker.build')}
        </Button>
      </BottomAction>
    </>
  )
}
