import { Route, Routes, useParams } from 'react-router-dom'

import { DisplayPage } from '@/pages/display/DisplayPage'

function DisplayPageRoute() {
  const { secretToken } = useParams<{ secretToken: string }>()
  return <DisplayPage secretToken={secretToken} />
}

export function DisplayRoutes() {
  return (
    <Routes>
      <Route path=":secretToken" element={<DisplayPageRoute />} />
    </Routes>
  )
}
