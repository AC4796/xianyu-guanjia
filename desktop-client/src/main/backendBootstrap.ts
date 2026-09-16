/**
 * 桌面端后端自举：只用安装包内自带 Python；自动接管 8080；保证 admin 可登录。
 */
import { app } from 'electron'
import { join, dirname } from 'path'
import { createWriteStream, existsSync, mkdirSync } from 'fs'
import { access } from 'fs/promises'
import { constants as fsConstants } from 'fs'
import { spawn, spawnSync, type ChildProcess } from 'child_process'
import http from 'http'
import nodeNet from 'net'

export const BACKEND_HOST = '127.0.0.1'
export const BACKEND_PORT = 8080

export type BackendStatus = {
  ready: boolean
  starting: boolean
  message: string
  projectRoot: string
  python: string
}

type PythonRuntime = { cmd: string; prefixArgs: string[] }

let backendProcess: ChildProcess | null = null
let ensurePromise: Promise<BackendStatus> | null = null
let status: BackendStatus = {
  ready: false,
  starting: false,
  message: '未检查',
  projectRoot: '',
  python: ''
}

export function getBackendStatus(): BackendStatus {
  return { ...status }
}

function setStatus(partial: Partial<BackendStatus>): BackendStatus {
  status = { ...status, ...partial }
  return status
}

export function isPortOpen(port: number, host = BACKEND_HOST): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = nodeNet.connect({ port, host })
    socket.once('connect', () => {
      socket.end()
      resolve(true)
    })
    socket.once('error', () => resolve(false))
  })
}

async function pathExists(p: string): Promise<boolean> {
  try {
    await access(p, fsConstants.F_OK)
    return true
  } catch {
    return false
  }
}

function logsDir(): string {
  const dir = join(app.getPath('userData'), 'runtime', 'logs')
  mkdirSync(dir, { recursive: true })
  return dir
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/** 探测当前 8080 是否可用 admin/admin123 登录 */
function probeAdminLogin(): Promise<boolean> {
  return new Promise((resolve) => {
    const body = JSON.stringify({ username: 'admin', password: 'admin123' })
    const req = http.request(
      {
        hostname: BACKEND_HOST,
        port: BACKEND_PORT,
        path: '/login',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body)
        },
        timeout: 5000
      },
      (res) => {
        let data = ''
        res.on('data', (c) => {
          data += c
        })
        res.on('end', () => {
          try {
            const j = JSON.parse(data)
            resolve(!!j?.success)
          } catch {
            resolve(false)
          }
        })
      }
    )
    req.on('error', () => resolve(false))
    req.on('timeout', () => {
      req.destroy()
      resolve(false)
    })
    req.write(body)
    req.end()
  })
}

/** 释放本机 8080（可能被旧进程占用且密码不对） */
function freePort(port: number): void {
  try {
    spawnSync(
      'powershell.exe',
      [
        '-NoProfile',
        '-Command',
        `Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }`
      ],
      { windowsHide: true, timeout: 15_000 }
    )
  } catch {
    /* ignore */
  }
}

export async function resolveProjectRoot(): Promise<string> {
  const candidates: string[] = []
  if (process.env.XIANYU_PROJECT_ROOT) candidates.push(process.env.XIANYU_PROJECT_ROOT)
  if (process.resourcesPath) candidates.push(join(process.resourcesPath, 'project'))
  candidates.push(join(dirname(process.execPath), 'resources', 'project'))
  candidates.push(join(dirname(process.execPath), 'project'))
  if (!app.isPackaged) {
    candidates.push(join(__dirname, '../../..'))
  }
  for (const root of candidates) {
    if (root && (await pathExists(join(root, 'Start.py')))) return root
  }
  return ''
}

function resolvePython(): PythonRuntime | null {
  const bundledCandidates = [
    process.resourcesPath ? join(process.resourcesPath, 'python', 'python.exe') : '',
    join(dirname(process.execPath), 'resources', 'python', 'python.exe'),
    join(__dirname, '../../bundled-runtime/python/python.exe')
  ].filter(Boolean)

  for (const exe of bundledCandidates) {
    if (existsSync(exe)) return { cmd: exe, prefixArgs: [] }
  }

  if (!app.isPackaged) {
    for (const t of [
      { cmd: 'py', prefixArgs: ['-3'] },
      { cmd: 'python', prefixArgs: [] }
    ]) {
      const r = spawnSync(t.cmd, [...t.prefixArgs, '-c', 'import sys; print(sys.version)'], {
        windowsHide: true,
        encoding: 'utf8',
        timeout: 8000
      })
      if (r.status === 0 && !(r.stdout || '').toLowerCase().includes('windowsapps')) {
        return t
      }
    }
  }
  return null
}

function runPython(
  py: PythonRuntime,
  args: string[],
  cwd: string
): { status: number | null; stdout: string; stderr: string } {
  const r = spawnSync(py.cmd, [...py.prefixArgs, ...args], {
    cwd,
    windowsHide: true,
    encoding: 'utf8',
    timeout: 90_000,
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      PYTHONPATH: cwd,
      XIANYU_DESKTOP: '1'
    }
  })
  return { status: r.status, stdout: String(r.stdout || ''), stderr: String(r.stderr || '') }
}

function ensureAdmin(py: PythonRuntime, projectRoot: string): void {
  // 用 -c 显式注入路径，兼容嵌入式 Python 的 ._pth 隔离
  const code = `
import os, sys
from pathlib import Path
root = Path(r'''${projectRoot.replace(/\\/g, '\\\\')}''')
os.chdir(root)
sys.path.insert(0, str(root))
from ensure_admin import ensure_admin
ensure_admin()
`
  const r = runPython(py, ['-c', code], projectRoot)
  if (r.status !== 0) {
    console.warn('[backend] ensure_admin failed', r.stderr || r.stdout)
  } else {
    console.log('[backend] ensure_admin ok', (r.stdout || '').trim())
  }
}

function spawnBackend(py: PythonRuntime, projectRoot: string): void {
  const startPy = join(projectRoot, 'Start.py')
  const logFile = join(logsDir(), 'backend.log')
  const out = createWriteStream(logFile, { flags: 'a' })

  backendProcess = spawn(py.cmd, [...py.prefixArgs, startPy], {
    cwd: projectRoot,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      PYTHONPATH: projectRoot,
      XIANYU_DESKTOP: '1',
      API_HOST: '127.0.0.1',
      API_PORT: String(BACKEND_PORT)
    }
  })
  backendProcess.stdout?.pipe(out)
  backendProcess.stderr?.pipe(out)
  backendProcess.on('exit', (code) => {
    console.log('[backend] exited', code)
    backendProcess = null
    if (!status.ready) {
      setStatus({
        starting: false,
        message: '本地服务启动失败，请点击「刷新二维码」重试'
      })
    }
  })
}

export async function ensureBackend(): Promise<BackendStatus> {
  if (ensurePromise) return ensurePromise
  ensurePromise = doEnsureBackend().finally(() => {
    ensurePromise = null
  })
  return ensurePromise
}

async function doEnsureBackend(): Promise<BackendStatus> {
  setStatus({ starting: true, ready: false, message: '正在准备本地服务…' })

  const projectRoot = await resolveProjectRoot()
  setStatus({ projectRoot })
  if (!projectRoot || !(await pathExists(join(projectRoot, 'Start.py')))) {
    return setStatus({
      ready: false,
      starting: false,
      message: '发布包不完整（缺少后端文件），请重新下载完整压缩包'
    })
  }

  const py = resolvePython()
  if (!py) {
    return setStatus({
      ready: false,
      starting: false,
      message: '发布包不完整（缺少内置运行环境），请重新下载完整压缩包',
      python: ''
    })
  }
  setStatus({ python: py.cmd })

  // 8080 已有服务：能登录就复用，否则杀掉重建（避免旧进程密码不对）
  if (await isPortOpen(BACKEND_PORT)) {
    setStatus({ message: '正在检查本地服务…' })
    if (await probeAdminLogin()) {
      return setStatus({ ready: true, starting: false, message: '本地服务已运行' })
    }
    setStatus({ message: '正在重置本地服务…' })
    freePort(BACKEND_PORT)
    killBackend()
    await sleep(1200)
  }

  setStatus({ message: '正在初始化账号…' })
  ensureAdmin(py, projectRoot)

  setStatus({ message: '正在启动本地服务…' })
  spawnBackend(py, projectRoot)

  for (let i = 0; i < 60; i++) {
    await sleep(1000)
    if (!(await isPortOpen(BACKEND_PORT))) {
      if (!backendProcess) {
        return setStatus({
          ready: false,
          starting: false,
          message: '本地服务启动失败，请点击「刷新二维码」重试'
        })
      }
      continue
    }
    // 服务起来后再确保一次管理员，并验证能登录
    ensureAdmin(py, projectRoot)
    await sleep(400)
    if (await probeAdminLogin()) {
      return setStatus({
        ready: true,
        starting: false,
        message: '本地服务已启动',
        projectRoot,
        python: py.cmd
      })
    }
    if (i >= 8) {
      // 仍登不上：再强刷一次 admin
      ensureAdmin(py, projectRoot)
      await sleep(500)
      if (await probeAdminLogin()) {
        return setStatus({ ready: true, starting: false, message: '本地服务已启动' })
      }
    }
  }

  return setStatus({
    ready: false,
    starting: false,
    message: '本地服务未能就绪，请点击「刷新二维码」重试'
  })
}

export function killBackend(): void {
  if (backendProcess && !backendProcess.killed) {
    try {
      backendProcess.kill()
    } catch {
      /* ignore */
    }
  }
  backendProcess = null
}

export async function resetAdminPassword(): Promise<{ ok: boolean; message: string }> {
  try {
    const projectRoot = status.projectRoot || (await resolveProjectRoot())
    const py = resolvePython()
    if (!py || !projectRoot) return { ok: false, message: '运行环境未就绪' }
    ensureAdmin(py, projectRoot)
    // 若当前服务登不上，重启我们自己的后端
    if (await isPortOpen(BACKEND_PORT)) {
      if (!(await probeAdminLogin())) {
        freePort(BACKEND_PORT)
        killBackend()
        await sleep(800)
        spawnBackend(py, projectRoot)
        for (let i = 0; i < 20; i++) {
          await sleep(500)
          if ((await isPortOpen(BACKEND_PORT)) && (await probeAdminLogin())) break
        }
      }
    }
    return { ok: true, message: '管理员已就绪' }
  } catch (e: any) {
    return { ok: false, message: String(e?.message || e) }
  }
}
