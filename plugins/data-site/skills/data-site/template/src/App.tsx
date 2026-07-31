import { useEffect, useState } from 'react'
import { AppShell } from '@/components/AppShell'
import { ConfigLoader } from '@/components/ConfigLoader'
import type { AppConfig } from '@/lib/schema'
import { parseConfig } from '@/lib/schema'
import exampleJson from '@/data/example.json'

const initial = parseConfig(exampleJson)

function App() {
  const [config, setConfig] = useState<AppConfig | null>(
    initial.ok ? initial.config : null,
  )
  const [source, setSource] = useState('example.json')
  const [version, setVersion] = useState(0)

  useEffect(() => {
    document.title = config?.title ?? 'Data site'
  }, [config])

  if (!config) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0a1120] p-8">
        <ul className="max-w-xl space-y-1 rounded-lg bg-red-500/10 p-4 font-mono text-xs text-red-300">
          {(initial.ok ? [] : initial.errors).map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <>
      <AppShell key={version} config={config} />
      <ConfigLoader
        sourceName={source}
        onConfig={(next, name) => {
          setConfig(next)
          setSource(name)
          setVersion((current) => current + 1)
        }}
      />
    </>
  )
}

export default App
