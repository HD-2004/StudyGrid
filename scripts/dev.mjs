import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const rawArgs = process.argv.slice(2)

function optionValue(name, fallback) {
  const inline = rawArgs.find((argument) => argument.startsWith(`${name}=`))
  if (inline) return inline.slice(name.length + 1)
  const index = rawArgs.indexOf(name)
  return index >= 0 && rawArgs[index + 1] ? rawArgs[index + 1] : fallback
}

function withoutOptions(args, names) {
  const result = []
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index]
    const exact = names.includes(argument)
    const inline = names.some((name) => argument.startsWith(`${name}=`))
    if (inline) continue
    if (exact) {
      index += 1
      continue
    }
    result.push(argument)
  }
  return result
}

function validPort(value, label) {
  const port = Number(value)
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error(`${label} must be an integer between 1 and 65535.`)
  }
  return port
}

const frontendPort = validPort(
  optionValue('--port', process.env.STUDYGRID_WEB_PORT ?? '5173'),
  'Frontend port',
)
const frontendHost = optionValue('--host', process.env.STUDYGRID_WEB_HOST ?? '127.0.0.1')
const apiPort = validPort(
  optionValue('--api-port', process.env.STUDYGRID_API_PORT ?? '8000'),
  'API port',
)
const apiHost = optionValue('--api-host', process.env.STUDYGRID_API_HOST ?? '127.0.0.1')
const healthHost = apiHost === '0.0.0.0' || apiHost === '::' ? '127.0.0.1' : apiHost
const apiTarget = process.env.STUDYGRID_API_TARGET ?? `http://${healthHost}:${apiPort}`
const frontendArgs = withoutOptions(rawArgs, ['--api-port', '--api-host'])

if (!rawArgs.some((argument) => argument === '--port' || argument.startsWith('--port='))) {
  frontendArgs.push('--port', String(frontendPort))
}
if (!rawArgs.some((argument) => argument === '--host' || argument.startsWith('--host='))) {
  frontendArgs.push('--host', frontendHost)
}

const python = process.platform === 'win32'
  ? join(root, '.venv', 'Scripts', 'python.exe')
  : join(root, '.venv', 'bin', 'python')

if (!existsSync(python)) {
  throw new Error(
    `Python virtual environment not found at ${python}. Create .venv and install requirements first.`,
  )
}

let apiProcess = null
let webProcess = null
let stopping = false

function terminateTree(child) {
  if (!child?.pid || child.exitCode !== null) return
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], {
      stdio: 'ignore',
      windowsHide: true,
    })
  } else {
    child.kill('SIGTERM')
  }
}

function stop(exitCode = 0) {
  if (stopping) return
  stopping = true
  terminateTree(webProcess)
  terminateTree(apiProcess)
  setTimeout(() => process.exit(exitCode), 350)
}

async function apiIsReady() {
  try {
    const response = await fetch(`${apiTarget}/health`, {
      signal: AbortSignal.timeout(750),
    })
    return response.ok && (await response.json()).status === 'ok'
  } catch {
    return false
  }
}

async function waitForApi() {
  const deadline = Date.now() + 20_000
  while (Date.now() < deadline) {
    if (apiProcess?.exitCode !== null) {
      throw new Error(`The StudyGrid API stopped with exit code ${apiProcess?.exitCode}.`)
    }
    if (await apiIsReady()) return
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250))
  }
  throw new Error(`The StudyGrid API did not become ready at ${apiTarget}/health.`)
}

process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))

try {
  if (await apiIsReady()) {
    console.log(`[StudyGrid] Reusing API at ${apiTarget}`)
  } else {
    console.log(`[StudyGrid] Starting API at ${apiTarget}`)
    apiProcess = spawn(
      python,
      ['-m', 'uvicorn', 'app.main:app', '--reload', '--host', apiHost, '--port', String(apiPort)],
      { cwd: root, env: process.env, stdio: 'inherit' },
    )
    apiProcess.once('error', (error) => {
      console.error(`[StudyGrid] Could not start API: ${error.message}`)
      stop(1)
    })
    await waitForApi()
  }

  const displayHost = frontendHost === '0.0.0.0' || frontendHost === '::' ? 'localhost' : frontendHost
  console.log(`[StudyGrid] Starting web app at http://${displayHost}:${frontendPort}`)
  const npmCli = process.env.npm_execpath
  const npmCommand = npmCli && existsSync(npmCli) ? process.execPath : 'npm'
  const npmArgs = npmCli && existsSync(npmCli)
    ? [npmCli, '--prefix', 'web', 'run', 'dev', '--', ...frontendArgs]
    : ['--prefix', 'web', 'run', 'dev', '--', ...frontendArgs]
  webProcess = spawn(npmCommand, npmArgs, {
    cwd: root,
    env: { ...process.env, STUDYGRID_API_TARGET: apiTarget },
    stdio: 'inherit',
  })
  webProcess.once('error', (error) => {
    console.error(`[StudyGrid] Could not start frontend: ${error.message}`)
    stop(1)
  })

  apiProcess?.once('exit', (code) => {
    if (!stopping) {
      console.error(`[StudyGrid] API stopped unexpectedly with exit code ${code}.`)
      stop(code ?? 1)
    }
  })
  webProcess.once('exit', (code) => {
    if (!stopping) {
      console.error(`[StudyGrid] Frontend stopped with exit code ${code}.`)
      stop(code ?? 0)
    }
  })
} catch (error) {
  console.error(`[StudyGrid] ${error instanceof Error ? error.message : String(error)}`)
  stop(1)
}
