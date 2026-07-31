import type { Column } from '@/lib/schema'
import { PAGE_KEY } from '@/lib/schema'
import { cn } from '@/lib/utils'

const alignClass = {
  left: 'text-left',
  center: 'text-center',
  right: 'text-right',
} as const

export function DataTable({
  columns,
  rows,
  onOpenPage,
  headerBg = 'bg-white',
}: {
  columns: Column[]
  rows: Record<string, string>[]
  onOpenPage?: (pageId: string) => void
  headerBg?: string
}) {
  return (
    <table className="w-full border-separate border-spacing-0 whitespace-nowrap text-[13px]">
      <thead className="sticky top-0 z-10">
        <tr>
          {columns.map((column) => (
            <th
              key={column.key}
              style={column.width ? { width: column.width } : undefined}
              className={cn(
                'border-b border-slate-200 px-4 py-2.5 font-medium text-slate-500',
                headerBg,
                alignClass[column.align ?? 'left'],
              )}
            >
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => {
          const pageId = row[PAGE_KEY]
          const openable = Boolean(pageId && onOpenPage)
          return (
            <tr
              key={index}
              className={cn('group', openable && 'cursor-pointer')}
              onClick={
                openable ? () => onOpenPage?.(pageId as string) : undefined
              }
            >
              {columns.map((column, columnIndex) => (
                <td
                  key={column.key}
                  className={cn(
                    'border-b border-slate-100 px-4 py-2.5 text-slate-700 group-hover:bg-slate-50/80',
                    alignClass[column.align ?? 'left'],
                    openable &&
                      columnIndex === 0 &&
                      'font-medium text-slate-900 group-hover:text-blue-700',
                  )}
                >
                  {row[column.key] ?? (
                    <span className="text-slate-300">&mdash;</span>
                  )}
                </td>
              ))}
            </tr>
          )
        })}
        {rows.length === 0 && (
          <tr>
            <td
              colSpan={columns.length}
              className="px-4 py-10 text-center text-slate-400"
            >
              No rows
            </td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
