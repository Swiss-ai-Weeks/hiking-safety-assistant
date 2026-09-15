import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { AppShell } from './components/AppShell'
import { AssessmentScreen } from './screens/AssessmentScreen'
import { FieldScreen } from './screens/FieldScreen'
import { PlanScreen } from './screens/PlanScreen'
import { PreflightScreen } from './screens/PreflightScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { ShareScreen } from './screens/ShareScreen'

// Leaflet is only needed on the map screen.
const RouteMapScreen = lazy(() => import('./screens/RouteMapScreen').then((m) => ({ default: m.RouteMapScreen })))

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <PlanScreen /> },
      { path: 'assessment', element: <AssessmentScreen /> },
      {
        path: 'assessment/map',
        element: (
          <Suspense fallback={<div className="flex-1 animate-pulse bg-subtle" />}>
            <RouteMapScreen />
          </Suspense>
        ),
      },
      { path: 'preflight', element: <PreflightScreen /> },
      { path: 'field', element: <FieldScreen /> },
      { path: 'share', element: <ShareScreen /> },
      { path: 'settings', element: <SettingsScreen /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
