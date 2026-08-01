import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { LoadingState } from '@/components/shared/LoadingState'
import { Toaster } from '@/components/ui/toast'
import { AuthProvider } from '@/contexts/AuthContext'

const AdminRoutes = lazy(() =>
  import('@/routes/AdminRoutes').then((module) => ({ default: module.AdminRoutes })),
)
const DisplayRoutes = lazy(() =>
  import('@/routes/DisplayRoutes').then((module) => ({ default: module.DisplayRoutes })),
)
const ParticipantRoutes = lazy(() =>
  import('@/routes/ParticipantRoutes').then((module) => ({ default: module.ParticipantRoutes })),
)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function RouteFallback() {
  return <LoadingState className="min-h-screen" label="Loading application…" />
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Navigate to="/admin" replace />} />
              <Route path="/admin/*" element={<AdminRoutes />} />
              <Route path="/display/*" element={<DisplayRoutes />} />
              <Route path="/*" element={<ParticipantRoutes />} />
            </Routes>
          </Suspense>
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
