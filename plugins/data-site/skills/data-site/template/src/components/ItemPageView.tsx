import type { ItemPage } from '@/lib/schema'
import { WidgetCard } from '@/components/WidgetCard'

export function ItemPageView({ page }: { page: ItemPage }) {
  return (
    <div className="min-h-0 flex-1 overflow-auto bg-slate-50/80 p-3">
      <div className="grid gap-3 lg:grid-cols-2">
        {page.widgets.map((widget, index) => (
          <WidgetCard key={`${widget.title}-${index}`} widget={widget} />
        ))}
      </div>
    </div>
  )
}
