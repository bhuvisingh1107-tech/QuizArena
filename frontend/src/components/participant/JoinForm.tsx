import { Loader2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useJoinMutation } from '@/hooks/queries/useJoin'
import { getParticipantRouteForRoomState } from '@/hooks/participantLiveReducer'
import {
  getOrCreateAnonymousEmail,
  getRememberedDisplayName,
  setRememberedDisplayName,
} from '@/lib/participant-identity'
import { ApiError } from '@/lib/participant-api'
import { joinFormSchema, type JoinFormValues } from '@/schemas/join'

interface JoinFormProps {
  initialRoomCode?: string
  roomCodeReadOnly?: boolean
  backLink?: ReactNode
}

export function JoinForm({
  initialRoomCode = '',
  roomCodeReadOnly = false,
  backLink,
}: JoinFormProps) {
  const navigate = useNavigate()
  const joinMutation = useJoinMutation()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<JoinFormValues>({
    resolver: zodResolver(joinFormSchema),
    defaultValues: {
      roomCode: initialRoomCode.toUpperCase(),
      displayName: getRememberedDisplayName(),
    },
  })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    const displayName = values.displayName.trim()
    const roomCode = values.roomCode.toUpperCase()
    setRememberedDisplayName(displayName)

    try {
      const result = await joinMutation.mutateAsync({
        roomCode,
        displayName,
        email: getOrCreateAnonymousEmail(),
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

  const pending = isSubmitting || joinMutation.isPending

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div className="space-y-2">
        <Label htmlFor="displayName">Your name</Label>
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
        <Label htmlFor="roomCode">Room code</Label>
        <Input
          id="roomCode"
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          placeholder="ABC123"
          readOnly={roomCodeReadOnly}
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

      {formError ? (
        <Alert variant="destructive">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <Button type="submit" size="lg" className="h-12 w-full" disabled={pending}>
        {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {pending ? 'Joining…' : 'Join room'}
      </Button>

      {backLink ? <div className="text-center">{backLink}</div> : null}
    </form>
  )
}
