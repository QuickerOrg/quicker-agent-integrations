import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  apply,
  loadWriteActionSkill,
  parseSkillMarkdown,
  writeActionSkillRegistration,
} from '../plugins/quicker-dsh/index.js'

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

function assertIncludes(haystack, needle, label) {
  if (!String(haystack).includes(needle)) {
    throw new Error(`${label}: expected to include ${JSON.stringify(needle)}`)
  }
}

function assertThrows(label, fn, needle) {
  try {
    fn()
  } catch (error) {
    const text = String(error?.message ?? error)
    if (!text.includes(needle)) {
      throw new Error(`${label}: expected ${JSON.stringify(needle)}, got ${JSON.stringify(text)}`)
    }
    return
  }
  throw new Error(`${label}: expected to throw`)
}

async function assertRejects(label, fn, needle) {
  try {
    await fn()
  } catch (error) {
    const text = String(error?.message ?? error)
    if (!text.includes(needle)) {
      throw new Error(`${label}: expected ${JSON.stringify(needle)}, got ${JSON.stringify(text)}`)
    }
    return
  }
  throw new Error(`${label}: expected to reject`)
}

function createContext() {
  const skills = []
  const events = []
  const loaderCalls = []
  return {
    skills,
    events,
    loaderCalls,
    ctx: {
      loader: {
        create: async (spec) => {
          loaderCalls.push(spec)
          return 'mcp-1'
        },
        store: { 'mcp-1': {} },
        remove: async () => {},
      },
      effect: async (fn) => {
        const dispose = await fn()
        return dispose
      },
      on: (event) => {
        events.push(event)
      },
      skills: {
        register(skill) {
          skills.push(skill)
          return () => {}
        },
      },
    },
  }
}

const parsed = parseSkillMarkdown('---\nname: write-action\ndescription: Route to Quicker authoring.\n---\n# Body\n')
assertEqual(parsed.name, 'write-action', 'parsed name')
assertEqual(parsed.description, 'Route to Quicker authoring.', 'parsed description')
assertEqual(parsed.content, '# Body', 'parsed content')
assertThrows(
  'missing frontmatter',
  () => parseSkillMarkdown('# Body\n'),
  'missing YAML frontmatter',
)
assertThrows(
  'missing description',
  () => parseSkillMarkdown('---\nname: write-action\n---\n# Body\n'),
  'requires name and description',
)

const skillFile = join(dirname(fileURLToPath(import.meta.url)), '..', 'plugins', 'quicker-dsh', 'skills', 'write-action', 'SKILL.md')
const fromDisk = loadWriteActionSkill()
const source = readFileSync(skillFile, 'utf8')
assertEqual(fromDisk.name, 'write-action', 'disk skill name')
assertIncludes(source, fromDisk.description, 'disk description comes from SKILL.md')
assertIncludes(fromDisk.content, 'quicker_create', 'disk skill body')
assert(
  !fromDisk.content.includes('---\nname: write-action'),
  'registered body must not include YAML frontmatter',
)

const registration = writeActionSkillRegistration(fromDisk)
assertEqual(registration.name, 'write-action', 'registration name')
assertEqual(registration.description, fromDisk.description, 'registration description stays compact')
assertEqual(registration.source, 'bundled', 'registration source')
assertEqual(registration.resourceBase.kind, 'directory', 'resourceBase kind')
assertIncludes(registration.resourceBase.path, 'write-action', 'resourceBase path')
assertIncludes(registration.content, 'mcp__quicker__skill_load', 'DSH tool names')
assertIncludes(registration.content, fromDisk.content.slice(0, 40), 'full skill body is on-demand content')
assert(
  registration.description.length < 500,
  `catalog card description must stay under DSH's 500-char bound, got ${registration.description.length}`,
)

const { ctx, skills, events, loaderCalls } = createContext()
await apply(ctx)
assertEqual(loaderCalls.length, 1, 'mcp client registrations')
assertEqual(loaderCalls[0].name, '@deepseek-ai/dsh-mcp-client', 'mcp client package')
assertEqual(loaderCalls[0].config.serverName, 'quicker', 'mcp serverName')
assertEqual(skills.length, 1, 'skill registrations')
assertEqual(skills[0].name, 'write-action', 'registered skill name')
assertEqual(skills[0].description, fromDisk.description, 'registered description is the catalog card')
assertIncludes(skills[0].content, 'mcp__quicker__quicker_create', 'registered body')
assertEqual(events.length, 0, 'no session-start or other conversation inject listeners')
assert(
  !JSON.stringify(skills[0].description).includes('# Write a Quicker action'),
  'catalog card must not contain the full skill body',
)

await assertRejects(
  'missing skills',
  () => apply({
    loader: { create: async () => 'mcp-1' },
    effect: async (fn) => fn(),
    on() {},
  }),
  'requires ctx.skills',
)

process.stdout.write(JSON.stringify({
  ok: true,
  skill: skills[0].name,
  descriptionChars: skills[0].description.length,
  contentChars: skills[0].content.length,
  mcpClient: loaderCalls[0].name,
  injectedEvents: events,
}) + '\n')
