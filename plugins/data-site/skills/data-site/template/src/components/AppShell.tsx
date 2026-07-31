import { useState } from 'react'
import { ChevronLeft } from 'lucide-react'
import type { AppConfig, NavItem, Section } from '@/lib/schema'
import { resolveIcon } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { DataTable } from '@/components/DataTable'
import { ItemPageView } from '@/components/ItemPageView'

type Location = { sectionId: string; itemId: string; pageId?: string }

function firstItem(section: Section): NavItem {
  return section.panel.groups[0].items[0]
}

function findSection(config: AppConfig, sectionId: string): Section {
  return config.sections.find((s) => s.id === sectionId) ?? config.sections[0]
}

function findItem(section: Section, itemId: string): NavItem {
  for (const group of section.panel.groups) {
    const match = group.items.find((item) => item.id === itemId)
    if (match) return match
  }
  return firstItem(section)
}

export function AppShell({ config }: { config: AppConfig }) {
  const [location, setLocation] = useState<Location>({
    sectionId: config.sections[0].id,
    itemId: firstItem(config.sections[0]).id,
  })
  const [history, setHistory] = useState<Location[]>([])

  const section = findSection(config, location.sectionId)
  const item = findItem(section, location.itemId)

  const go = (next: Location) => {
    if (
      next.sectionId === location.sectionId &&
      next.itemId === location.itemId &&
      next.pageId === location.pageId
    )
      return
    setHistory((past) => [...past, location])
    setLocation(next)
  }

  const back = () => {
    setHistory((past) => {
      if (past.length === 0) return past
      setLocation(past[past.length - 1])
      return past.slice(0, -1)
    })
  }

  const view = item.view
  const page = location.pageId ? config.pages[location.pageId] : undefined
  const HeaderIcon = resolveIcon(page ? page.icon : (view.icon ?? item.icon))
  const PanelIcon = resolveIcon(section.panel.icon ?? section.icon)

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-[#0a1120] text-slate-300">
      <header className="flex h-11 shrink-0 items-center px-3">
        <button
          type="button"
          onClick={back}
          disabled={history.length === 0}
          aria-label="Back"
          className="grid h-7 w-7 place-items-center rounded-md text-slate-400 transition hover:bg-white/10 hover:text-white disabled:pointer-events-none disabled:opacity-30"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav className="flex w-14 shrink-0 flex-col items-center gap-1 pb-3">
          {config.sections.map((entry) => {
            const Icon = resolveIcon(entry.icon)
            const active = entry.id === section.id
            return (
              <button
                key={entry.id}
                type="button"
                title={entry.label}
                onClick={() =>
                  go({
                    sectionId: entry.id,
                    itemId: firstItem(entry).id,
                  })
                }
                className={cn(
                  'flex w-12 flex-col items-center gap-0.5 rounded-lg py-1.5 transition',
                  active
                    ? 'bg-white/10 text-white'
                    : 'text-slate-500 hover:bg-white/5 hover:text-slate-200',
                )}
              >
                <Icon className="h-[18px] w-[18px]" />
                {active && (
                  <span className="max-w-full truncate text-[9px] font-medium tracking-wide">
                    {entry.label}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        <aside className="mb-2 flex w-60 shrink-0 flex-col overflow-hidden rounded-xl bg-[#131d33] ring-1 ring-white/[0.06]">
          <div className="flex items-center gap-2 px-3 py-3">
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-emerald-500/15 text-emerald-300">
              <PanelIcon className="h-3.5 w-3.5" />
            </span>
            <span className="truncate text-[13px] font-semibold text-white">
              {section.panel.title}
            </span>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
            {section.panel.groups.map((group, groupIndex) => (
              <div key={group.label ?? groupIndex} className="mb-3">
                {group.label && (
                  <div className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    {group.label}
                  </div>
                )}
                <ul className="space-y-0.5">
                  {group.items.map((entry) => {
                    const Icon = resolveIcon(entry.icon)
                    const active = entry.id === item.id
                    return (
                      <li key={entry.id}>
                        <button
                          type="button"
                          onClick={() =>
                            go({ sectionId: section.id, itemId: entry.id })
                          }
                          className={cn(
                            'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] transition',
                            active
                              ? 'bg-blue-500/15 font-medium text-white'
                              : 'text-slate-400 hover:bg-white/5 hover:text-slate-100',
                          )}
                        >
                          <Icon
                            className={cn(
                              'h-3.5 w-3.5 shrink-0',
                              active ? 'text-blue-300' : 'text-slate-500',
                            )}
                          />
                          <span className="truncate">{entry.label}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </div>
        </aside>

        <main className="ml-2 flex min-w-0 flex-1 flex-col overflow-hidden rounded-tl-2xl bg-white">
          <div className="flex shrink-0 items-center gap-2.5 border-b border-slate-200 px-5 py-3.5">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-blue-50 text-blue-600 ring-1 ring-blue-100">
              <HeaderIcon className="h-4 w-4" />
            </span>
            <h1 className="text-[17px] font-semibold tracking-tight text-slate-900">
              {page ? page.title : (view.title ?? item.label)}
            </h1>
          </div>

          {page ? (
            <ItemPageView page={page} />
          ) : (
            <div className="min-h-0 flex-1 overflow-auto">
              <DataTable
                columns={view.columns}
                rows={view.rows}
                onOpenPage={(pageId) =>
                  go({
                    sectionId: section.id,
                    itemId: item.id,
                    pageId,
                  })
                }
              />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
