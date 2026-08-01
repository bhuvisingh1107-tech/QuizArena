import { Route, Routes, useParams } from 'react-router-dom'

import { DisplayShell } from '@/components/display/DisplayShell'
import { ErrorState } from '@/components/shared/ErrorState'
import { DisplayPage } from '@/pages/display/DisplayPage'

function DisplayPageRoute() {
  const { secretToken } = useParams<{ secretToken: string }>()
  return <DisplayPage secretToken={secretToken} />
}

function MissingDisplayToken() {
  return (
    <DisplayShell connectionStatus="disconnected">
      <div className="flex flex-1 items-center justify-center">
        <ErrorState
          title="Display unavailable"
          message="This presentation link is missing a token. Open the display URL from the host monitor."
        />
      </div>
    </DisplayShell>
  )
}

export function DisplayRoutes() {
  return (
    <Routes>
      <Route index element={<MissingDisplayToken />} />
      <Route path=":secretToken" element={<DisplayPageRoute />} />
      <Route path="*" element={<MissingDisplayToken />} />
    </Routes>
  )
}
