import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { OptionList } from '@/components/participant/OptionList'
import { SubmitBar } from '@/components/participant/SubmitBar'

const options = [
  { id: 'o1', text: 'Alpha', sortOrder: 0 },
  { id: 'o2', text: 'Beta', sortOrder: 1 },
]

describe('OptionList / SubmitBar duplicate submit guard', () => {
  it('does not change selection when already submitted', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(
      <OptionList
        options={options}
        selectedOptionIds={['o1']}
        submissionStatus="submitted"
        onChange={onChange}
      />,
    )

    await user.click(screen.getByRole('option', { name: /beta/i }))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('disables submit button while submitting or submitted', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    const { rerender } = render(
      <SubmitBar
        submissionStatus="submitting"
        canSubmit
        onSubmit={onSubmit}
      />,
    )

    expect(screen.getByRole('button', { name: /submitting/i })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /submitting/i }))
    expect(onSubmit).not.toHaveBeenCalled()

    rerender(
      <SubmitBar submissionStatus="submitted" canSubmit onSubmit={onSubmit} />,
    )
    expect(screen.getByRole('button', { name: /submitted/i })).toBeDisabled()
  })
})
