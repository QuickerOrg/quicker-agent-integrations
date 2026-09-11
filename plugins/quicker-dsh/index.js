import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PACKAGE_ROOT = dirname(fileURLToPath(import.meta.url))
const RELAY_SCRIPT = 'quicker-mcp.ps1'
const SKILL_FILE = join(PACKAGE_ROOT, 'skills', 'write-action', 'SKILL.md')

export const name = 'quicker'
export const inject = ['tools']

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

function injectAuthoringGuide(agent) {
  try {
    agent.inject({
      content: [{ type: 'text', text: authoringPreamble() }],
      source: { kind: 'plugin', plugin: 'dsh-plugin-quicker' },
    })
  } catch {
    // A disposed agent must not fail plugin activation.
  }
}

export function apply(ctx) {
  ctx.plugin('@deepseek-ai/dsh-mcp-client', mcpClientConfig())
  ctx.on('agent/session-start', ({ agent }) => {
    injectAuthoringGuide(agent)
  })
}
