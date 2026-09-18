import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, RouterProvider, useLocation, useSearchParams } from 'react-router'
import { AppShell } from './components/AppShell'
import { PlanScreen } from './screens/PlanScreen'
import { RoutePickerScreen } from './screens/RoutePickerScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { ShareScreen } from './screens/ShareScreen'
import { usePlan } from './store/plan'

// Leaflet is only needed on the screens with a map.
const BriefingScreen = lazy(() => import('./screens/BriefingScreen').then((m) => ({ default: m.BriefingScreen })))
const FieldScreen = lazy(() => import('./screens/FieldScreen').then((m) => ({ default: m.FieldScreen })))
const RouteMapScreen = lazy(() => import('./screens/RouteMapScreen').then((m) => ({ default: m.RouteMapScreen })))

const mapFallback = <div className="flex-1 animate-pulse bg-subtle" />

/**
 * Screens about a planned hike, which there is none of until a route is picked: those go to search.
 * A `?routeId=` link is let through, because `AppShell` is about to plan that route.
 */
function RequireRoute({ children }: { children: ReactNode }) {
  const routeId = usePlan((s) => s.routeId)
  const [params] = useSearchParams()
  if (routeId !== null) return children
  return params.has('routeId') ? null : <Navigate to="/routes/new" replace />
}

/** The briefing replaced the assessment and "before you go" screens; old links land on it. */
function ToBriefing({ step }: { step?: number }) {
  const { search } = useLocation()
  const params = new URLSearchParams(search)
  if (step) params.set('step', String(step))
  const query = params.toString()
  return <Navigate to={`/briefing${query ? `?${query}` : ''}`} replace />
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      {
        index: true,
        element: (
          <RequireRoute>
            <PlanScreen />
          </RequireRoute>
        ),
      },
      { path: 'routes/new', element: <RoutePickerScreen /> },
      {
        path: 'briefing',
        element: (
          <RequireRoute>
            <Suspense fallback={mapFallback}>
              <BriefingScreen />
            </Suspense>
          </RequireRoute>
        ),
      },
      {
        path: 'map',
        element: (
          <RequireRoute>
            <Suspense fallback={mapFallback}>
              <RouteMapScreen />
            </Suspense>
          </RequireRoute>
        ),
      },
      { path: 'assessment', element: <ToBriefing /> },
      { path: 'assessment/map', element: <Navigate to="/map" replace /> },
      { path: 'preflight', element: <ToBriefing step={5} /> },
      {
        path: 'field',
        element: (
          <RequireRoute>
            <Suspense fallback={mapFallback}>
              <FieldScreen />
            </Suspense>
          </RequireRoute>
        ),
      },
      {
        path: 'share',
        element: (
          <RequireRoute>
            <ShareScreen />
          </RequireRoute>
        ),
      },
      { path: 'settings', element: <SettingsScreen /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
