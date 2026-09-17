import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PACKAGE_ROOT = dirname(fileURLToPath(import.meta.url))
const RELAY_SCRIPT = 'quicker-mcp.ps1'
const SKILL_DIR = join(PACKAGE_ROOT, 'skills', 'write-action')
const SKILL_FILE = join(SKILL_DIR, 'SKILL.md')
const DSH_TOOL_NOTE = [
  'Quicker MCP tools appear as mcp__quicker__<toolName>',
  '(for example mcp__quicker__skill_load and mcp__quicker__quicker_create).',
  'They edit Quicker virtual slots, not this workspace.',
].join(' ')

export const name = 'quicker'
export const inject = ['tools', 'loader', 'skills']

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

function unquoteYamlScalar(value) {
  if (
    (value.startsWith('"') && value.endsWith('"'))
    || (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1)
  }
  return value
}

export function parseSkillMarkdown(markdown) {
  const match = /^\uFEFF?---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(markdown)
  if (!match) {
    throw new Error('write-action skill is missing YAML frontmatter')
  }

  const fields = {}
  for (const line of match[1].split(/\r?\n/)) {
    const separator = line.indexOf(':')
    if (separator <= 0) continue
    const key = line.slice(0, separator).trim()
    const value = unquoteYamlScalar(line.slice(separator + 1).trim())
    if (key !== '') fields[key] = value
  }

  const name = fields.name?.trim()
  const description = fields.description?.trim()
  if (!name || !description) {
    throw new Error('write-action skill frontmatter requires name and description')
  }

  return {
    name,
    description,
    content: match[2].trim(),
  }
}

export function loadWriteActionSkill() {
  return parseSkillMarkdown(readFileSync(SKILL_FILE, 'utf8'))
}

export function writeActionSkillRegistration(skill = loadWriteActionSkill()) {
  return {
    name: skill.name,
    description: skill.description,
    content: `${DSH_TOOL_NOTE}\n\n${skill.content}`,
    source: 'bundled',
    path: SKILL_FILE,
    resourceBase: { kind: 'directory', path: SKILL_DIR },
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
  if (ctx.skills == null || typeof ctx.skills.register !== 'function') {
    throw new Error('dsh-plugin-quicker requires ctx.skills to register the write-action skill')
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

  // Register a catalog card only. DSH's skill tool loads the body on demand
  // (`skill({ name: "write-action" })` or `/write-action`). Do not inject the
  // full guide into every session — that crowds out unrelated conversations.
  await ctx.effect(
    () => ctx.skills.register(writeActionSkillRegistration()),
    'dsh-plugin-quicker: write-action',
  )
}
