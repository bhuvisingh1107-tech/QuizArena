import { Navigate, Route, Routes } from 'react-router-dom'

import { AdminLayout } from '@/layouts/AdminLayout'
import { CreateQuizPage } from '@/pages/admin/CreateQuizPage'
import { DashboardPage } from '@/pages/admin/DashboardPage'
import { EditQuizPage } from '@/pages/admin/EditQuizPage'
import { LiveRoomsPage } from '@/pages/admin/LiveRoomsPage'
import { LoginPage } from '@/pages/admin/LoginPage'
import { MediaPage } from '@/pages/admin/MediaPage'
import { QuestionEditorPage } from '@/pages/admin/QuestionEditorPage'
import { QuizzesPage } from '@/pages/admin/QuizzesPage'
import { ResultsPage } from '@/pages/admin/ResultsPage'
import { RoomMonitorPage } from '@/pages/admin/RoomMonitorPage'
import { RoomResultsPage } from '@/pages/admin/RoomResultsPage'
import { SettingsPage } from '@/pages/admin/SettingsPage'
import { ProtectedRoute } from '@/routes/ProtectedRoute'

export function AdminRoutes() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AdminLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          <Route path="quizzes" element={<QuizzesPage />} />
          <Route path="quizzes/new" element={<CreateQuizPage />} />
          <Route path="quizzes/:quizId" element={<EditQuizPage />} />
          <Route path="quizzes/:quizId/questions" element={<QuestionEditorPage />} />
          <Route
            path="quizzes/:quizId/sections/:sectionId/questions/:questionId"
            element={<QuestionEditorPage />}
          />

          <Route path="media" element={<MediaPage />} />

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
