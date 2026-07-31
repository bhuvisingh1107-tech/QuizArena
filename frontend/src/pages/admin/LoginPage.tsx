import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/hooks/queries/useAuth'
import { ApiError } from '@/lib/api-client'
import { loginSchema, type LoginFormValues } from '@/schemas/login'

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: '', password: '' },
  })

  if (!isLoading && isAuthenticated) {
    const from = (location.state as { from?: string } | null)?.from ?? '/admin/dashboard'
    return <Navigate to={from} replace />
  }

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      await login(values)
      navigate('/admin/dashboard', { replace: true })
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message)
      } else {
        setFormError('Unable to sign in. Please try again.')
      }
    }
  })

  return (
    <div className="relative flex min-h-svh items-center justify-center px-4 py-12">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -left-24 top-1/4 h-72 w-72 rounded-full bg-[var(--primary)]/10 blur-3xl" />
        <div className="absolute -right-16 bottom-1/4 h-80 w-80 rounded-full bg-[var(--accent)]/10 blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        <div className="mb-10 text-center">
          <p className="font-display text-5xl font-extrabold tracking-tight text-[#f0f4fa] sm:text-6xl">
            Quiz<span className="text-[var(--primary)]">Arena</span>
          </p>
          <p className="mt-3 text-sm text-[var(--muted-foreground)]">
            Host live quizzes with precision control.
          </p>
        </div>

        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/90 p-8 shadow-[0_20px_60px_rgba(0,0,0,0.35)] backdrop-blur">
          <div className="mb-6">
            <h1 className="font-display text-2xl font-semibold text-[#f0f4fa]">Admin sign in</h1>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Use your administrator credentials to open the console.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-5" noValidate>
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoComplete="username"
                placeholder="admin"
                aria-invalid={Boolean(errors.username)}
                {...register('username')}
              />
              {errors.username ? (
                <p className="text-xs text-[var(--destructive)]" role="alert">
                  {errors.username.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••••••"
                aria-invalid={Boolean(errors.password)}
                {...register('password')}
              />
              {errors.password ? (
                <p className="text-xs text-[var(--destructive)]" role="alert">
                  {errors.password.message}
                </p>
              ) : null}
            </div>

            {formError ? (
              <Alert variant="destructive">
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            ) : null}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-[var(--muted-foreground)]">
          Secured admin access · JWT session
        </p>
      </div>
    </div>
  )
}
