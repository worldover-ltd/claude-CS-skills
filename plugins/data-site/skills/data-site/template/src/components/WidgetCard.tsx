import type { Widget, WorkflowSection } from '@/lib/schema'
import { resolveIcon } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { DataTable } from '@/components/DataTable'

function FieldsSection({
  section,
}: {
  section: Extract<WorkflowSection, { type: 'fields' }>
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {section.fields.map((field) => (
        <div key={field.label}>
          <div className="pb-1 text-[11px] text-slate-500">{field.label}</div>
          <div className="rounded-md border border-slate-200 bg-slate-50/70 px-3 py-1.5 text-[13px] text-slate-700">
            {field.value ?? <span className="text-slate-300">&mdash;</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function ItemsSection({
  section,
}: {
  section: Extract<WorkflowSection, { type: 'items' }>
}) {
  return (
    <ul className="space-y-1.5">
      {section.items.map((item) => {
        const Icon = resolveIcon(item.icon ?? 'file')
        return (
          <li
            key={item.label}
            className="flex items-center gap-2 text-[13px] text-slate-700"
          >
            <Icon className="h-3.5 w-3.5 shrink-0 text-slate-400" />
            <span>{item.label}</span>
          </li>
        )
      })}
    </ul>
  )
}

export function WidgetCard({ widget }: { widget: Widget }) {
  return (
    <section
      className={cn(
        'flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white',
        widget.span === 'full' && 'lg:col-span-2',
      )}
    >
      <header className="border-b border-slate-200 px-4 py-2.5 text-[13px] font-semibold text-slate-800">
        {widget.title}
      </header>

      {widget.type === 'table' ? (
        <div className="overflow-x-auto">
          <DataTable columns={widget.columns} rows={widget.rows} />
        </div>
      ) : (
        <div className="space-y-3 p-4">
          {widget.sections.map((section) => (
            <div
              key={section.label}
              className="rounded-lg border border-slate-200/80 p-3"
            >
              <div className="pb-2.5 text-[11px] font-medium uppercase tracking-wide text-blue-600/80">
                {section.label}
              </div>
              {section.type === 'fields' ? (
                <FieldsSection section={section} />
              ) : (
                <ItemsSection section={section} />
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
