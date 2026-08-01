import { Navigate, Route, Routes, useParams } from 'react-router-dom'

import { AdminLayout } from '@/layouts/AdminLayout'
import { DashboardPage } from '@/pages/admin/DashboardPage'
import { LiveRoomsPage } from '@/pages/admin/LiveRoomsPage'
import { LoginPage } from '@/pages/admin/LoginPage'
import { QuizBuilderPage } from '@/pages/admin/QuizBuilderPage'
import { QuizzesPage } from '@/pages/admin/QuizzesPage'
import { ResultsPage } from '@/pages/admin/ResultsPage'
import { RoomMonitorPage } from '@/pages/admin/RoomMonitorPage'
import { RoomResultsPage } from '@/pages/admin/RoomResultsPage'
import { SettingsPage } from '@/pages/admin/SettingsPage'
import { ProtectedRoute } from '@/routes/ProtectedRoute'

function RedirectToBuilderQuestions() {
  const { quizId = '' } = useParams()
  return <Navigate to={`/admin/quizzes/${quizId}?step=2`} replace />
}

export function AdminRoutes() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AdminLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          <Route path="quizzes" element={<QuizzesPage />} />
          <Route path="quizzes/new" element={<QuizBuilderPage />} />
          <Route path="quizzes/:quizId" element={<QuizBuilderPage />} />
          <Route path="quizzes/:quizId/questions" element={<RedirectToBuilderQuestions />} />
          <Route
            path="quizzes/:quizId/sections/:sectionId/questions/:questionId"
            element={<RedirectToBuilderQuestions />}
          />

          <Route path="media" element={<Navigate to="/admin/quizzes" replace />} />

          <Route path="live-rooms" element={<LiveRoomsPage />} />
          <Route path="live-rooms/:roomId" element={<RoomMonitorPage />} />

          <Route path="results" element={<ResultsPage />} />
          <Route path="results/:roomId" element={<RoomResultsPage />} />

          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/admin/dashboard" replace />} />
    </Routes>
  )
}
