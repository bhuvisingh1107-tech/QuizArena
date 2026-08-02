import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

function Probe() {
  const params = useParams()
  return <pre data-testid="params">{JSON.stringify(params)}</pre>
}

function DisplayRoutes() {
  return (
    <Routes>
      <Route index element={<div>missing</div>} />
      <Route path=":secretToken" element={<Probe />} />
      <Route path="*" element={<div>missing-star</div>} />
    </Routes>
  )
}

describe('display nested splat params', () => {
  it('captures secretToken from /display/:token via nested Routes', async () => {
    const token = 'GY6H6n_EcxQvvT_w2SVJehPhsE5xQZdeGakJ76w4Ngg'
    render(
      <MemoryRouter initialEntries={[`/display/${token}`]}>
        <Routes>
          <Route path="/display/*" element={<DisplayRoutes />} />
        </Routes>
      </MemoryRouter>,
    )
    const el = await screen.findByTestId('params')
    expect(el.textContent).toContain(token)
    expect(el.textContent).toContain('secretToken')
  })
})
