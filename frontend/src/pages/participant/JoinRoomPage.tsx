import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useJoinMutation } from '@/hooks/queries/useJoin'
import { ApiError } from '@/lib/participant-api'
import { getParticipantRouteForRoomState } from '@/hooks/participantLiveReducer'
import { joinIdentitySchema, type JoinIdentityFormValues } from '@/schemas/join'

export function JoinRoomPage() {
  const { roomCode: roomCodeParam = '' } = useParams()
  const navigate = useNavigate()
  const joinMutation = useJoinMutation()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<JoinIdentityFormValues>({
    resolver: zodResolver(joinIdentitySchema),
    defaultValues: {
      roomCode: roomCodeParam.toUpperCase(),
      displayName: '',
      email: '',
    },
  })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      const result = await joinMutation.mutateAsync({
        roomCode: values.roomCode.toUpperCase(),
        displayName: values.displayName.trim(),
        email: values.email.trim().toLowerCase(),
      })
      const route = getParticipantRouteForRoomState(result.room.state) ?? '/lobby'
      navigate(route, { replace: true })
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message)
      } else {
        setFormError('Unable to join. Please try again.')
      }
    }
  })

  return (
    <ParticipantShell subtitle={`Room ${roomCodeParam.toUpperCase() || '—'}`}>
      <div className="flex flex-1 flex-col justify-center">
        <div className="mb-8 text-center">
          <h1 className="font-display text-3xl font-bold text-[#f0f4fa]">Join the lobby</h1>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Pick a display name and enter the email your host expects.
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-5" noValidate>
          <div className="space-y-2">
            <Label htmlFor="roomCode">Room code</Label>
            <Input
              id="roomCode"
              autoComplete="off"
              className="h-12 font-display tracking-[0.2em] uppercase"
              aria-invalid={Boolean(errors.roomCode)}
              {...register('roomCode')}
            />
            {errors.roomCode ? (
              <p className="text-xs text-[var(--destructive)]" role="alert">
                {errors.roomCode.message}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="displayName">Display name</Label>
            <Input
              id="displayName"
              autoComplete="nickname"
              placeholder="Alex"
              className="h-12"
              aria-invalid={Boolean(errors.displayName)}
              {...register('displayName')}
            />
            {errors.displayName ? (
              <p className="text-xs text-[var(--destructive)]" role="alert">
                {errors.displayName.message}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              className="h-12"
              aria-invalid={Boolean(errors.email)}
              {...register('email')}
            />
            {errors.email ? (
              <p className="text-xs text-[var(--destructive)]" role="alert">
                {errors.email.message}
              </p>
            ) : null}
          </div>

          {formError ? (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          <Button
            type="submit"
            size="lg"
            className="h-12 w-full"
            disabled={isSubmitting || joinMutation.isPending}
          >
            {isSubmitting || joinMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {isSubmitting || joinMutation.isPending ? 'Joining…' : 'Join room'}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-[var(--muted-foreground)]">
          <Link to="/join" className="text-[var(--primary)] underline-offset-2 hover:underline">
            Different room code?
          </Link>
        </p>
      </div>
    </ParticipantShell>
  )
}
