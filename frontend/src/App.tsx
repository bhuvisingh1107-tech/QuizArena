import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { LoadingState } from '@/components/shared/LoadingState'
import { Toaster } from '@/components/ui/toast'
import { AuthProvider } from '@/contexts/AuthContext'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/admin/LoginPage'
import { SignupPage } from '@/pages/host/SignupPage'

const AdminRoutes = lazy(() =>
  import('@/routes/AdminRoutes').then((module) => ({ default: module.AdminRoutes })),
)
const DisplayRoutes = lazy(() =>
  import('@/routes/DisplayRoutes').then((module) => ({ default: module.DisplayRoutes })),
)
const DisplayPageRoute = lazy(() =>
  import('@/routes/DisplayRoutes').then((module) => ({ default: module.DisplayPageRoute })),
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
              <Route path="/" element={<LandingPage />} />
              <Route path="/host/login" element={<LoginPage />} />
              <Route path="/host/signup" element={<SignupPage />} />
              <Route path="/admin/login" element={<Navigate to="/host/login" replace />} />
              <Route path="/dashboard" element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="/admin/*" element={<AdminRoutes />} />
              <Route path="/display/:secretToken" element={<DisplayPageRoute />} />
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
