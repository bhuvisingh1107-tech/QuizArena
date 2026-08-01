import type { ReactNode } from 'react'

import { EmptyState } from '@/components/shared/EmptyState'
import { LoadingState } from '@/components/shared/LoadingState'
import { Table, TableBody, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

interface DataTableProps {
  columns: ReactNode
  children: ReactNode
  loading?: boolean
  loadingLabel?: string
  empty?: boolean
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  className?: string
}

export function DataTable({
  columns,
  children,
  loading,
  loadingLabel = 'Loading…',
  empty,
  emptyTitle = 'No results',
  emptyDescription,
  emptyAction,
  className,
}: DataTableProps) {
  if (loading) {
    return <LoadingState label={loadingLabel} />
  }

  if (empty) {
    return (
      <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
    )
  }

  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--card)]/60',
        className,
      )}
    >
      <Table>
        <TableHeader>
          <TableRow>{columns}</TableRow>
        </TableHeader>
        <TableBody>{children}</TableBody>
      </Table>
    </div>
  )
}
