import { useEffect, useRef, useState } from 'react'
import { FileJson, Upload, X } from 'lucide-react'
import type { AppConfig } from '@/lib/schema'
import { parseConfigText } from '@/lib/schema'

export function ConfigLoader({
  onConfig,
  sourceName,
}: {
  onConfig: (config: AppConfig, name: string) => void
  sourceName: string
}) {
  const [open, setOpen] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [text, setText] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const apply = (raw: string, name: string) => {
    const result = parseConfigText(raw)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors([])
    onConfig(result.config, name)
    setOpen(false)
  }

  const readFile = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => apply(String(reader.result), file.name)
    reader.readAsText(file)
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-3 right-3 z-50 flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-medium text-slate-300 ring-1 ring-white/15 backdrop-blur transition hover:bg-white/20 hover:text-white"
      >
        <FileJson className="h-3.5 w-3.5" />
        {sourceName}
      </button>
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/60 p-4"
      onClick={() => setOpen(false)}
    >
      <div
        role="dialog"
        aria-label="Load config"
        onClick={(event) => event.stopPropagation()}
        className="relative w-full max-w-lg space-y-3 rounded-xl bg-white p-5 shadow-2xl"
      >
        <button
          type="button"
          aria-label="Close"
          onClick={() => setOpen(false)}
          className="absolute right-3 top-3 grid h-7 w-7 place-items-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
        >
          <X className="h-4 w-4" />
        </button>

        <div>
          <h2 className="text-sm font-semibold text-slate-900">Load config</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Drop a <code>.json</code> file, pick one, or paste it. Validated with
            Zod before render.
          </p>
        </div>

        <div
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault()
            const file = event.dataTransfer.files[0]
            if (file) readFile(file)
          }}
          onClick={() => fileInput.current?.click()}
          className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500 transition hover:border-slate-400 hover:bg-slate-50"
        >
          <Upload className="h-4 w-4" />
          Drop JSON here or click to browse
          <input
            ref={fileInput}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) readFile(file)
              event.target.value = ''
            }}
          />
        </div>

        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          spellCheck={false}
          placeholder={'{\n  "sections": [ ... ]\n}'}
          className="h-32 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-700 outline-none focus:border-slate-400"
        />

        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => apply(text, 'pasted JSON')}
            disabled={text.trim().length === 0}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700 disabled:opacity-40"
          >
            Render pasted JSON
          </button>
        </div>

        {errors.length > 0 && (
          <ul className="max-h-32 space-y-1 overflow-auto rounded-lg bg-red-50 p-3 font-mono text-[11px] text-red-700">
            {errors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
