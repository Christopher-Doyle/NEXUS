import { spawn } from 'node:child_process'
import { existsSync, mkdtempSync, realpathSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative, resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const webRoot = resolve(import.meta.dirname, '..')
const repoRoot = resolve(webRoot, '../..')
const apiRoot = join(repoRoot, 'services', 'api')
const python = process.env.NEXUS_PYTHON || join(apiRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
if (!existsSync(python)) throw new Error(`Python environment not found: ${python}. Run uv sync --extra dev in services/api.`)
const tempBase = realpathSync(tmpdir())
const tempRoot = mkdtempSync(join(tempBase, 'nexus-e2e-'))
const database = join(tempRoot, 'nexus.db').replaceAll('\\', '/')
const env = { ...process.env, DATABASE_URL: `sqlite:///${database}`, DATA_DIR: tempRoot, OLLAMA_MODEL: process.env.NEXUS_E2E_OLLAMA_MODEL || '', APPROVED_WORKSPACES: '', DEMO_MODE: 'true' }
const children = []

function start(command, args, cwd) {
  const child = spawn(command, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  children.push(child)
  child.stdout.on('data', data => process.stdout.write(data))
  child.stderr.on('data', data => process.stderr.write(data))
  return child
}

async function run(command, args, cwd) {
  const child = start(command, args, cwd)
  const code = await new Promise((done, reject) => { child.once('exit', done); child.once('error', reject) })
  if (code !== 0) throw new Error(`${command} exited with ${code}`)
}

async function ready(url, child) {
  const deadline = Date.now() + 20_000
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`Service exited before ${url} became ready`)
    try { if ((await fetch(url)).ok) return } catch { /* Startup in progress. */ }
    await delay(250)
  }
  throw new Error(`Timed out waiting for ${url}`)
}

let exitCode = 1
try {
  await run(python, ['-m', 'alembic', 'upgrade', 'head'], apiRoot)
  const api = start(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8765', '--no-access-log'], apiRoot)
  await ready('http://127.0.0.1:8765/ready', api)
  start(python, ['-m', 'app.worker'], apiRoot)
  const web = start(process.execPath, [join(webRoot, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', '5173', '--strictPort'], webRoot)
  await ready('http://127.0.0.1:5173/', web)
  await run(process.execPath, [join(webRoot, 'node_modules', '@playwright', 'test', 'cli.js'), 'test', '--config', 'playwright.config.ts', ...process.argv.slice(2)], webRoot)
  exitCode = 0
} catch (error) {
  process.stderr.write(`${error.message}\n`)
} finally {
  const closing = []
  for (const child of children.reverse()) {
    if (child.exitCode === null && child.signalCode === null) {
      closing.push(Promise.race([new Promise(done => child.once('close', done)), delay(5000)]))
      child.kill()
    }
  }
  await Promise.all(closing)
  await delay(250)
  const resolved = realpathSync(tempRoot)
  const withinTemp = !isAbsolute(relative(tempBase, resolved)) && !relative(tempBase, resolved).startsWith('..')
  if (withinTemp && basename(resolved).startsWith('nexus-e2e-')) {
    try { rmSync(resolved, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 }) }
    catch (error) { process.stderr.write(`Could not clean isolated test data at ${resolved}: ${error.message}\n`); exitCode = 1 }
  }
}
process.exitCode = exitCode
