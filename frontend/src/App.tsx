import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouterProvider, useLocation } from 'react-router'
import { AppShell } from './components/AppShell'
import { PlanScreen } from './screens/PlanScreen'
import { RoutePickerScreen } from './screens/RoutePickerScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { ShareScreen } from './screens/ShareScreen'

// Leaflet is only needed on the screens with a map.
const BriefingScreen = lazy(() => import('./screens/BriefingScreen').then((m) => ({ default: m.BriefingScreen })))
const FieldScreen = lazy(() => import('./screens/FieldScreen').then((m) => ({ default: m.FieldScreen })))
const RouteMapScreen = lazy(() => import('./screens/RouteMapScreen').then((m) => ({ default: m.RouteMapScreen })))

const mapFallback = <div className="flex-1 animate-pulse bg-subtle" />

/** The briefing replaced the assessment and "before you go" screens; old links land on it, keeping `?outcome=`. */
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
      { index: true, element: <PlanScreen /> },
      { path: 'routes/new', element: <RoutePickerScreen /> },
      {
        path: 'briefing',
        element: (
          <Suspense fallback={mapFallback}>
            <BriefingScreen />
          </Suspense>
        ),
      },
      {
        path: 'map',
        element: (
          <Suspense fallback={mapFallback}>
            <RouteMapScreen />
          </Suspense>
        ),
      },
      { path: 'assessment', element: <ToBriefing /> },
      { path: 'assessment/map', element: <Navigate to="/map" replace /> },
      { path: 'preflight', element: <ToBriefing step={5} /> },
      {
        path: 'field',
        element: (
          <Suspense fallback={mapFallback}>
            <FieldScreen />
          </Suspense>
        ),
      },
      { path: 'share', element: <ShareScreen /> },
      { path: 'settings', element: <SettingsScreen /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
