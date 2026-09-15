import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { apply, createAuthoringGuideMessage } from '../plugins/quicker-dsh/index.js'

const sessionEntry = process.env.DSH_SESSION_ENTRY
if (!sessionEntry) {
  throw new Error('DSH_SESSION_ENTRY must point at @deepseek-ai/dsh-session/lib/index.js')
}
const { snapshotSessionEvent } = await import(pathToFileURL(sessionEntry).href)

function asUserMessageEvent(data, seq = 1) {
  return {
    type: 'user/message',
    seq,
    time: Date.now(),
    data,
    surfaceOp: 'append',
  }
}

function expectThrow(label, fn, needle) {
  try {
    fn()
  } catch (error) {
    const text = String(error?.message ?? error)
    if (!text.includes(needle)) {
      throw new Error(`${label}: expected ${JSON.stringify(needle)}, got ${JSON.stringify(text)}`)
    }
    return text
  }
  throw new Error(`${label}: expected DSH to reject the event`)
}

const broken = {
  content: [{ type: 'text', text: 'Quicker MCP tools are registered as mcp__quicker__<toolName>' }],
  source: { kind: 'plugin', plugin: 'dsh-plugin-quicker' },
}
const brokenError = expectThrow(
  '0.2.0 inject payload',
  () => snapshotSessionEvent(asUserMessageEvent(broken, 421)),
  'lacks an identified message',
)

const fixed = createAuthoringGuideMessage('guide')
const adopted = snapshotSessionEvent(asUserMessageEvent(fixed, 1))
if (adopted.data.id !== fixed.id || adopted.data.role !== 'user') {
  throw new Error('fixed inject lost id or role after DSH adopt')
}

const injected = []
const handlers = {}
await apply({
  loader: {
    create: async () => 'mcp-1',
    store: { 'mcp-1': {} },
    remove: async () => {},
  },
  effect: async (fn) => {
    await fn()
    return async () => {}
  },
  on: (event, handler) => {
    handlers[event] = handler
  },
})
handlers['agent/session-start']({ agent: { inject: (message) => injected.push(message) } })
if (injected.length !== 1) {
  throw new Error(`session-start should inject one guide, got ${injected.length}`)
}
snapshotSessionEvent(asUserMessageEvent(injected[0], 10))

const sessionPath = process.env.QUICKER_DSH_SESSION_JSONL
const evidence = []
if (sessionPath) {
  for (const line of readFileSync(sessionPath, 'utf8').split(/\r?\n/)) {
    if (!line.includes('dsh-plugin-quicker')) continue
    let event
    try {
      event = JSON.parse(line)
    } catch {
      continue
    }
    if (event?.type !== 'user/message') continue
    const plugin = event.data?.source?.plugin
    if (plugin !== 'dsh-plugin-quicker') continue
    try {
      snapshotSessionEvent(structuredClone(event))
      evidence.push({ seq: event.seq, ok: true })
    } catch (error) {
      evidence.push({ seq: event.seq, ok: false, error: String(error?.message ?? error) })
    }
  }
}

process.stdout.write(JSON.stringify({
  ok: true,
  brokenError,
  fixedId: adopted.data.id,
  injectedId: injected[0].id,
  evidence,
  plugin: new URL('../plugins/quicker-dsh/index.js', import.meta.url).href,
}) + '\n')
