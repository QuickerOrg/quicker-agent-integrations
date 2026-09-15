import { randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PACKAGE_ROOT = dirname(fileURLToPath(import.meta.url))
const RELAY_SCRIPT = 'quicker-mcp.ps1'
const SKILL_FILE = join(PACKAGE_ROOT, 'skills', 'write-action', 'SKILL.md')

export const name = 'quicker'
export const inject = ['tools', 'loader']

export function resolvePackageRoot() {
  return PACKAGE_ROOT
}

export function mcpClientConfig(root = PACKAGE_ROOT) {
  return {
    serverName: 'quicker',
    transport: 'stdio',
    command: 'powershell.exe',
    args: [
      '-NoLogo',
      '-NoProfile',
      '-NonInteractive',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      join(root, 'scripts', RELAY_SCRIPT),
      '-Client',
      'dsh',
    ],
    cwd: root,
    toolCallTimeoutMs: 180000,
    failOnStartupError: false,
  }
}

function loadWriteActionSkill() {
  try {
    return readFileSync(SKILL_FILE, 'utf8').trim()
  } catch {
    return [
      'Use Quicker MCP tools to create, edit, save and preview actions.',
      'Tool names are prefixed as mcp__quicker__<name>.',
      'Load action-source with skill_load before editing program.source.yaml.',
    ].join(' ')
  }
}

function authoringPreamble() {
  return [
    'Quicker MCP tools are registered as mcp__quicker__<toolName>',
    '(for example mcp__quicker__skill_load and mcp__quicker__quicker_create).',
    'They edit Quicker virtual slots, not the local workspace.',
    '',
    loadWriteActionSkill(),
  ].join('\n')
}

function assertIdentifiedUserMessage(message) {
  if (typeof message !== 'object' || message === null
    || typeof message.id !== 'string' || message.id === '') {
    throw new Error('dsh-plugin-quicker inject requires an identified message')
  }
  if (message.role !== 'user') {
    throw new Error('dsh-plugin-quicker inject requires role user')
  }
  if (typeof message.source !== 'object' || message.source === null
    || typeof message.source.kind !== 'string' || message.source.kind === '') {
    throw new Error('dsh-plugin-quicker inject requires a message source')
  }
  if (!Array.isArray(message.content)) {
    throw new Error('dsh-plugin-quicker inject requires content')
  }
}

export function createAuthoringGuideMessage(text) {
  const message = {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text: text ?? authoringPreamble() }],
    source: { kind: 'plugin', plugin: 'dsh-plugin-quicker' },
  }
  assertIdentifiedUserMessage(message)
  return message
}

function injectAuthoringGuide(agent) {
  const message = createAuthoringGuideMessage()
  try {
    // DSH persist + replay require a complete UserMessage (id + role).
    agent.inject(message)
  } catch {
    // A disposed agent must not fail plugin activation.
  }
}

export async function apply(ctx) {
  // Cordis ctx.plugin() only accepts a function or { apply }. Package names
  // must go through the DSH loader, which resolves host packages such as
  // @deepseek-ai/dsh-mcp-client from the desktop/CLI install.
  const loader = ctx.loader
  if (loader == null || typeof loader.create !== 'function') {
    throw new Error('dsh-plugin-quicker requires the DSH loader to register @deepseek-ai/dsh-mcp-client')
  }

  await ctx.effect(async () => {
    const id = await loader.create({
      name: '@deepseek-ai/dsh-mcp-client',
      config: mcpClientConfig(),
    })
    return async () => {
      if (loader.store?.[id] === undefined) return
      await loader.remove(id)
    }
  }, 'dsh-plugin-quicker: mcp-client')

  ctx.on('agent/session-start', ({ agent }) => {
    injectAuthoringGuide(agent)
  })
}
