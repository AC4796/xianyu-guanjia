import { app, shell, BrowserWindow, ipcMain, screen, dialog, net } from 'electron'
import { join, extname } from 'path'
import { writeFile } from 'fs/promises'
import { createReadStream, existsSync, statSync } from 'fs'
import http from 'http'
import type { IncomingMessage, ServerResponse } from 'http'
import type { AddressInfo } from 'net'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import nodeNet from 'net'
import {
  BACKEND_HOST,
  BACKEND_PORT,
  ensureBackend,
  getBackendStatus,
  killBackend,
  resetAdminPassword
} from './backendBootstrap'

let mainWindow: BrowserWindow | null = null
let gatewayServer: http.Server | null = null
let gatewayPort = 0

/** 需要反代到 FastAPI 的路径前缀（与 electron.vite.config 代理保持一致） */
const API_PREFIXES = [
  '/login',
  '/logout',
  '/verify',
  '/generate-captcha',
  '/verify-captcha',
  '/system-settings',
  '/automation-settings',
  '/ai-reply-settings',
  '/ai-reply-test',
  '/cookies',
  '/cookie',
  '/api',
  '/keywords',
  '/keywords-with-item-id',
  '/keywords-with-type',
  '/keywords-export',
  '/keywords-import',
  '/items',
  '/cards',
  '/orders',
  '/item-replies',
  '/item-reply',
  '/itemReplays',
  '/upload-image',
  '/static',
  '/chat',
  '/admin',
  '/message-notifications',
  '/notification-channels',
  '/delivery-rules',
  '/default-reply',
  '/default-replies',
  '/user-settings',
  '/analytics',
  '/qr-login',
  '/password-login',
  '/backup',
  '/change-password',
  '/change-admin-password',
  '/ws',
  '/seller-watch',
  '/dropship-jobs',
  '/yanghao',
  '/sensitive',
  '/health',
  '/xianyu'
]

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json'
}

function shouldProxyApi(pathname: string): boolean {
  return API_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + '/'))
}

function proxyHttpToBackend(req: IncomingMessage, res: ServerResponse): void {
  const headers = { ...req.headers, host: `${BACKEND_HOST}:${BACKEND_PORT}` }
  const opts: http.RequestOptions = {
    hostname: BACKEND_HOST,
    port: BACKEND_PORT,
    path: req.url,
    method: req.method,
    headers
  }
  const upstream = http.request(opts, (upRes) => {
    res.writeHead(upRes.statusCode || 502, upRes.headers)
    upRes.pipe(res)
  })
  upstream.on('error', (err) => {
    console.error('[gateway] proxy error', err.message)
    const st = getBackendStatus()
    if (!res.headersSent) {
      res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
    }
    res.end(
      JSON.stringify({
        success: false,
        message: st.starting
          ? '本地服务启动中，请稍候再刷新'
          : st.message || '后端未启动或不可达(8080)'
      })
    )
  })
  req.pipe(upstream)
}

function proxyWsToBackend(req: IncomingMessage, socket: any, head: Buffer): void {
  const upstream = nodeNet.connect(BACKEND_PORT, BACKEND_HOST, () => {
    const lines = [
      `${req.method} ${req.url} HTTP/${req.httpVersion}`,
      ...Object.entries(req.headers).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`),
      '',
      ''
    ]
    upstream.write(lines.join('\r\n'))
    if (head && head.length) upstream.write(head)
    socket.pipe(upstream)
    upstream.pipe(socket)
  })
  upstream.on('error', () => {
    try {
      socket.destroy()
    } catch {
      /* ignore */
    }
  })
  socket.on('error', () => {
    try {
      upstream.destroy()
    } catch {
      /* ignore */
    }
  })
}

async function serveRendererFile(pathname: string, res: ServerResponse): Promise<void> {
  const root = join(__dirname, '../renderer')
  let rel = decodeURIComponent(pathname.split('?')[0] || '/')
  if (rel === '/' || rel === '') rel = '/index.html'
  // 防止路径穿越
  const filePath = join(root, rel.replace(/^\/+/, ''))
  if (!filePath.startsWith(root)) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }
  let target = filePath
  if (!existsSync(target) || (existsSync(target) && statSync(target).isDirectory())) {
    // SPA fallback
    target = join(root, 'index.html')
  }
  if (!existsSync(target)) {
    res.writeHead(404)
    res.end('Not Found')
    return
  }
  const ext = extname(target).toLowerCase()
  res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
  createReadStream(target).pipe(res)
}

/**
 * 打包后不走 file://（Cookie SameSite 跨源会丢会话），
 * 改为本机同源 HTTP 网关：页面 + /qr-login 等 API 同属 127.0.0.1:port
 */
function startDesktopGateway(): Promise<number> {
  if (gatewayServer && gatewayPort) return Promise.resolve(gatewayPort)

  const server = http.createServer((req, res) => {
    const pathname = (req.url || '/').split('?')[0] || '/'
    if (shouldProxyApi(pathname)) {
      proxyHttpToBackend(req, res)
      return
    }
    void serveRendererFile(pathname, res)
  })

  server.on('upgrade', (req, socket, head) => {
    const pathname = (req.url || '/').split('?')[0] || '/'
    if (pathname.startsWith('/ws') || shouldProxyApi(pathname)) {
      proxyWsToBackend(req, socket, head)
      return
    }
    socket.destroy()
  })

  gatewayServer = server
  return new Promise((resolve, reject) => {
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address() as AddressInfo
      gatewayPort = addr.port
      console.log('[gateway] listening http://127.0.0.1:' + gatewayPort)
      resolve(gatewayPort)
    })
    server.on('error', reject)
  })
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

async function createWindow(): Promise<void> {
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
    const port = await startDesktopGateway()
    mainWindow.loadURL(`http://127.0.0.1:${port}/`)
  }
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.xianyuguanjia.desktop')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  ipcMain.handle('app:getVersion', () => app.getVersion())
  ipcMain.handle('app:getBackendStatus', () => getBackendStatus())
  ipcMain.handle('app:ensureBackend', async () => ensureBackend())
  ipcMain.handle('app:resetAdmin', async () => resetAdminPassword())
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

  // 先开窗口，后端自举在界面里显示进度（避免装依赖时黑屏假死）
  void ensureBackend()
  await createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  if (gatewayServer) {
    try {
      gatewayServer.close()
    } catch {
      /* ignore */
    }
    gatewayServer = null
  }
  killBackend()
})
