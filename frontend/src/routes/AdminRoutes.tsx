import { Navigate, Route, Routes, useParams } from 'react-router-dom'

import { AdminLayout } from '@/layouts/AdminLayout'
import { AiGeneratePage } from '@/pages/admin/AiGeneratePage'
import { AiReviewPage } from '@/pages/admin/AiReviewPage'
import { CreateQuizChooserPage } from '@/pages/admin/CreateQuizChooserPage'
import { DashboardPage } from '@/pages/admin/DashboardPage'
import { LiveRoomsPage } from '@/pages/admin/LiveRoomsPage'
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
      <Route path="login" element={<Navigate to="/host/login" replace />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AdminLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          <Route path="quizzes" element={<QuizzesPage />} />
          {/* Static paths before :quizId so "ai" / "new" never hit the builder */}
          <Route path="quizzes/ai" element={<AiGeneratePage />} />
          <Route path="quizzes/ai/:jobId" element={<AiReviewPage />} />
          <Route path="quizzes/new" element={<CreateQuizChooserPage />} />
          <Route path="quizzes/new/manual" element={<QuizBuilderPage />} />
          <Route path="ai" element={<Navigate to="/admin/quizzes/ai" replace />} />
          <Route path="ai/:jobId" element={<AiReviewRedirect />} />
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
          <Route path="profile" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/admin/dashboard" replace />} />
    </Routes>
  )
}

function AiReviewRedirect() {
  const { jobId = '' } = useParams()
  return <Navigate to={`/admin/quizzes/ai/${jobId}`} replace />
}
