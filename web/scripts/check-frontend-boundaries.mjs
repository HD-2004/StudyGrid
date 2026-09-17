import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const SOURCE_EXTENSIONS = new Set(['.js', '.mjs', '.cjs', '.ts', '.svelte'])
const ALLOWED_FETCH_FILE = 'src/lib/api.ts'
const FETCH_REFERENCE = /\bfetch\b/
const FETCH_CALL = /\b(?:globalThis\s*\.\s*|window\s*\.\s*)?fetch\s*\(/
const PLACEMENT_PATTERNS = [
  ['frontend allocator reference', /\b[A-Za-z_$][\w$]*Allocator\b/],
  ['legacy AI placement state', /\b(?:AiPreview|proposedStart|proposedEnd)\b/],
  ['automatic placement helper', /\b(?:findSuggestedMove|applyAiPreview|find(?:Available|Open|Free|Suggested)Slot|allocateSlot|auto(?:matic)?Placement|autoSchedule)\b/i],
  ['automatic slot-search helper', /\b(?:find|choose|allocate|compute|suggest)\w*(?:Available|Open|Free|Automatic|Suggested)\w*(?:Slot|Time|Move)\b/i],
]

function maskNonCode(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/\/\/[^\r\n]*/g, ' ')
    .replace(/'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`/gs, ' ')
}

export function analyzeSource(relativePath, source) {
  const code = maskNonCode(source)
  const violations = []
  if (relativePath !== ALLOWED_FETCH_FILE && FETCH_REFERENCE.test(code)) {
    violations.push('fetch reference outside the canonical API client')
  }
  for (const [label, pattern] of PLACEMENT_PATTERNS) {
    if (pattern.test(code)) violations.push(label)
  }
  return violations
}

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async (entry) => {
    const target = path.join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(target)
    return SOURCE_EXTENSIONS.has(path.extname(entry.name)) ? [target] : []
  }))
  return nested.flat()
}

export async function checkFrontendBoundaries(srcRoot) {
  const findings = []
  let canonicalFetchFound = false
  for (const file of await sourceFiles(srcRoot)) {
    const relativePath = path.relative(path.dirname(srcRoot), file).replaceAll('\\', '/')
    const source = await readFile(file, 'utf8')
    const code = maskNonCode(source)
    if (relativePath === ALLOWED_FETCH_FILE && FETCH_CALL.test(code)) canonicalFetchFound = true
    for (const violation of analyzeSource(relativePath, source)) findings.push(`${relativePath}: ${violation}`)
  }
  if (!canonicalFetchFound) findings.push(`${ALLOWED_FETCH_FILE}: canonical fetch call is missing`)
  return findings
}

async function main() {
  const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const findings = await checkFrontendBoundaries(path.join(webRoot, 'src'))
  if (findings.length) {
    console.error(`Frontend architecture boundary violations:\n- ${findings.join('\n- ')}`)
    process.exitCode = 1
  } else console.log('[ok] fetch is isolated to lib/api.ts; no frontend automatic placement found')
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main()
