import { app, shell, BrowserWindow, ipcMain, screen, dialog, net } from 'electron'
import { join, dirname } from 'path'
import { writeFile, access } from 'fs/promises'
import { constants as fsConstants } from 'fs'
import { spawn, type ChildProcess } from 'child_process'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import nodeNet from 'net'

let backendProcess: ChildProcess | null = null
let mainWindow: BrowserWindow | null = null

function isPortOpen(port: number, host = '127.0.0.1'): Promise<boolean> {
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

/** 开发态：desktop-client/out/main → 项目根；安装包：探测常见路径 / 环境变量 */
async function resolveProjectRoot(): Promise<string> {
  const candidates = [
    process.env.XIANYU_PROJECT_ROOT || '',
    join(__dirname, '../../..'),
    join(process.resourcesPath || '', 'project'),
    join(dirname(process.execPath), 'project'),
    join(dirname(process.execPath), '..', 'project'),
    // 本机 phpstudy 常见路径
    'D:\\phpstudy_pro\\WWW\\闲鱼管家',
    'd:\\phpstudy_pro\\WWW\\闲鱼管家'
  ].filter(Boolean)
  for (const root of candidates) {
    if (await pathExists(join(root, 'Start.py'))) return root
  }
  return candidates[1] || candidates[0]
}

async function ensureBackend(): Promise<void> {
  if (await isPortOpen(8080)) {
    console.log('[backend] 8080 already running')
    return
  }
  const projectRoot = await resolveProjectRoot()
  const startPy = join(projectRoot, 'Start.py')
  if (!(await pathExists(startPy))) {
    console.warn('[backend] Start.py not found, skip auto start. root=', projectRoot)
    return
  }
  console.log('[backend] starting', startPy)
  backendProcess = spawn('python', [startPy], {
    cwd: projectRoot,
    windowsHide: true,
    stdio: 'ignore'
  })
  backendProcess.on('exit', (code) => {
    console.log('[backend] exited', code)
    backendProcess = null
  })
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 1000))
    if (await isPortOpen(8080)) {
      console.log('[backend] ready')
      return
    }
  }
  console.warn('[backend] not ready after waiting')
}

type WindowMode = 'login' | 'workbench'

/** 登录窗紧凑；工作台更大；都按屏幕自适应，笔记本不撑爆 */
function calcWindowSize(mode: WindowMode): {
  width: number
  height: number
  minWidth: number
  minHeight: number
} {
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize
  if (mode === 'login') {
    const width = Math.round(Math.min(880, Math.max(720, sw * 0.52)))
    const height = Math.round(Math.min(560, Math.max(480, sh * 0.58)))
    return {
      width: Math.min(width, sw - 24),
      height: Math.min(height, sh - 24),
      minWidth: Math.min(680, sw - 40),
      minHeight: Math.min(460, sh - 40)
    }
  }
  const width = Math.round(Math.min(1440, Math.max(1100, sw * 0.86)))
  const height = Math.round(Math.min(900, Math.max(720, sh * 0.86)))
  return {
    width: Math.min(width, sw - 24),
    height: Math.min(height, sh - 24),
    minWidth: Math.min(980, Math.max(860, sw - 80)),
    minHeight: Math.min(640, Math.max(580, sh - 80))
  }
}

function applyWindowMode(win: BrowserWindow, mode: WindowMode): void {
  const size = calcWindowSize(mode)
  win.setMinimumSize(size.minWidth, size.minHeight)
  win.setSize(size.width, size.height, true)
  win.center()
}

function createWindow(): void {
  const size = calcWindowSize('login')
  mainWindow = new BrowserWindow({
    width: size.width,
    height: size.height,
    minWidth: size.minWidth,
    minHeight: size.minHeight,
    show: false,
    title: '闲鱼管家',
    icon,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
    mainWindow?.focus()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.xianyuguanjia.desktop')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  ipcMain.handle('app:getVersion', () => app.getVersion())
  ipcMain.handle('app:getOpenAtLogin', () => {
    try {
      const s = app.getLoginItemSettings()
      return { openAtLogin: !!s.openAtLogin, openAsHidden: !!s.openAsHidden }
    } catch {
      return { openAtLogin: false, openAsHidden: false }
    }
  })
  ipcMain.handle('app:setOpenAtLogin', (_e, enabled: boolean) => {
    try {
      const openAtLogin = !!enabled
      if (app.isPackaged) {
        app.setLoginItemSettings({ openAtLogin, openAsHidden: false })
      } else {
        // 开发态：登记当前 Electron + 项目入口，便于本机验证开关是否生效
        app.setLoginItemSettings({
          openAtLogin,
          openAsHidden: false,
          path: process.execPath,
          args: [app.getAppPath()]
        })
      }
      const s = app.getLoginItemSettings()
      return { ok: true, openAtLogin: !!s.openAtLogin }
    } catch (err: any) {
      return { ok: false, openAtLogin: false, message: String(err?.message || err) }
    }
  })
  ipcMain.handle('window:setMode', (_e, mode: WindowMode) => {
    if (!mainWindow || mainWindow.isDestroyed()) return false
    if (mode !== 'login' && mode !== 'workbench') return false
    applyWindowMode(mainWindow, mode)
    return true
  })
  ipcMain.handle('file:saveRemote', async (_e, url: string, defaultName = '') => {
    try {
      const win = BrowserWindow.getFocusedWindow() || mainWindow
      const result = await dialog.showSaveDialog(win || undefined, {
        title: '选择保存位置',
        defaultPath: defaultName || 'download.bin',
        properties: ['createDirectory', 'showOverwriteConfirmation']
      })
      if (result.canceled || !result.filePath) return { ok: false }
      const target = result.filePath
      // data URL
      if (String(url).startsWith('data:')) {
        const m = String(url).match(/^data:[^;]+;base64,(.+)$/)
        if (!m) return { ok: false }
        await writeFile(target, Buffer.from(m[1], 'base64'))
        return { ok: true, path: target }
      }
      const res = await net.fetch(String(url))
      if (!res.ok) return { ok: false }
      const buf = Buffer.from(await res.arrayBuffer())
      await writeFile(target, buf)
      return { ok: true, path: target }
    } catch {
      return { ok: false }
    }
  })

  await ensureBackend()
  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  if (backendProcess && !backendProcess.killed) {
    try {
      backendProcess.kill()
    } catch {
      /* ignore */
    }
  }
})
