import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Toaster } from '@/components/ui/toast'
import { AuthProvider } from '@/contexts/AuthContext'
import { AdminRoutes } from '@/routes/AdminRoutes'
import { DisplayRoutes } from '@/routes/DisplayRoutes'
import { ParticipantRoutes } from '@/routes/ParticipantRoutes'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<Navigate to="/admin" replace />} />
            <Route path="/admin/*" element={<AdminRoutes />} />
            <Route path="/display/*" element={<DisplayRoutes />} />
            <Route path="/*" element={<ParticipantRoutes />} />
          </Routes>
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
