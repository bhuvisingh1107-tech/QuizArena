import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { joinRoomCodeSchema, type JoinRoomCodeFormValues } from '@/schemas/join'

export function JoinPage() {
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<JoinRoomCodeFormValues>({
    resolver: zodResolver(joinRoomCodeSchema),
    defaultValues: { roomCode: '' },
  })

  const onSubmit = handleSubmit((values) => {
    navigate(`/join/${values.roomCode}`)
  })

  return (
    <ParticipantShell subtitle="Join a live quiz">
      <div className="flex flex-1 flex-col justify-center">
        <div className="mb-8 text-center">
          <h1 className="font-display text-3xl font-bold text-[#f0f4fa]">Enter room code</h1>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Ask your host for the 6-character code.
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-5" noValidate>
          <div className="space-y-2">
            <Label htmlFor="roomCode">Room code</Label>
            <Input
              id="roomCode"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              placeholder="ABC123"
              className="h-12 text-center font-display text-xl tracking-[0.3em] uppercase"
              aria-invalid={Boolean(errors.roomCode)}
              {...register('roomCode')}
            />
            {errors.roomCode ? (
              <p className="text-xs text-[var(--destructive)]" role="alert">
                {errors.roomCode.message}
              </p>
            ) : null}
          </div>

          <Button type="submit" size="lg" className="h-12 w-full" disabled={isSubmitting}>
            Continue
          </Button>
        </form>

        <p className="mt-8 text-center text-xs text-[var(--muted-foreground)]">
          Hosting instead?{' '}
          <Link to="/admin/login" className="text-[var(--primary)] underline-offset-2 hover:underline">
            Admin sign in
          </Link>
        </p>
      </div>
    </ParticipantShell>
  )
}
