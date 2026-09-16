/**
 * 预置便携 Python + 依赖到 bundled-runtime/python
 * 打包时打进 resources/python，对方电脑无需安装任何环境
 *
 * 用法：node scripts/prepare-bundled-runtime.mjs
 */
import {
  createWriteStream,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  unlinkSync,
  rmSync
} from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'
import { spawnSync } from 'child_process'
import http from 'http'
import https from 'https'

const __dirname = dirname(fileURLToPath(import.meta.url))
const clientRoot = join(__dirname, '..')
const projectRoot = join(clientRoot, '..')
const outDir = join(clientRoot, 'bundled-runtime', 'python')
const marker = join(outDir, '.deps-ready')
const reqFile = existsSync(join(projectRoot, 'requirements-desktop.txt'))
  ? join(projectRoot, 'requirements-desktop.txt')
  : join(projectRoot, 'requirements.txt')

const PYTHON_EMBED_URL =
  'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip'
const GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py'

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = createWriteStream(dest)
    const lib = url.startsWith('https') ? https : http
    const req = lib.get(url, { timeout: 180_000 }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close()
        try {
          unlinkSync(dest)
        } catch {
          /* ignore */
        }
        download(res.headers.location, dest).then(resolve, reject)
        return
      }
      if (res.statusCode !== 200) {
        reject(new Error(`下载失败 ${res.statusCode}: ${url}`))
        return
      }
      res.pipe(file)
      file.on('finish', () => file.close(() => resolve()))
    })
    req.on('error', reject)
    req.on('timeout', () => {
      req.destroy()
      reject(new Error('下载超时'))
    })
  })
}

function run(cmd, args, opts = {}) {
  console.log('>', cmd, args.join(' '))
  const r = spawnSync(cmd, args, {
    cwd: opts.cwd || outDir,
    windowsHide: true,
    encoding: 'utf8',
    timeout: opts.timeout || 900_000,
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      PIP_DISABLE_PIP_VERSION_CHECK: '1'
    }
  })
  if (r.stdout) process.stdout.write(r.stdout)
  if (r.stderr) process.stderr.write(r.stderr)
  if (r.status !== 0) {
    throw new Error(`命令失败: ${cmd} ${args.join(' ')}`)
  }
}

function patchPth() {
  for (const name of ['python311._pth', 'python310._pth', 'python312._pth']) {
    const p = join(outDir, name)
    if (!existsSync(p)) continue
    let text = readFileSync(p, 'utf8')
    text = text.replace(/^#\s*import site/m, 'import site')
    if (!text.includes('import site')) text += '\nimport site\n'
    if (!text.includes('Lib\\site-packages')) text += 'Lib\\site-packages\n'
    writeFileSync(p, text, 'utf8')
  }
  mkdirSync(join(outDir, 'Lib', 'site-packages'), { recursive: true })
}

async function main() {
  const pyExe = join(outDir, 'python.exe')
  if (existsSync(pyExe) && existsSync(marker)) {
    // 快速校验核心依赖
    const check = spawnSync(
      pyExe,
      [
        '-c',
        'import fastapi,uvicorn,loguru,yaml,aiohttp,requests,httpx,pandas,PIL,jwt,passlib,multipart,qrcode,execjs,blackboxprotobuf; print("ok")'
      ],
      { windowsHide: true, encoding: 'utf8', timeout: 30_000 }
    )
    if (check.status === 0) {
      console.log('bundled-runtime 已就绪，跳过准备')
      return
    }
    console.log('bundled-runtime 存在但依赖不完整，重新安装…')
  }

  mkdirSync(join(clientRoot, 'bundled-runtime'), { recursive: true })
  const zipPath = join(clientRoot, 'bundled-runtime', 'python-embed.zip')
  const getPip = join(clientRoot, 'bundled-runtime', 'get-pip.py')

  if (!existsSync(pyExe)) {
    console.log('下载便携 Python 3.11…')
    await download(PYTHON_EMBED_URL, zipPath)
    if (existsSync(outDir)) rmSync(outDir, { recursive: true, force: true })
    mkdirSync(outDir, { recursive: true })
    run('powershell.exe', [
      '-NoProfile',
      '-Command',
      `Expand-Archive -LiteralPath '${zipPath.replace(/'/g, "''")}' -DestinationPath '${outDir.replace(/'/g, "''")}' -Force`
    ])
    patchPth()
  } else {
    patchPth()
  }

  if (!existsSync(getPip)) {
    console.log('下载 get-pip.py…')
    await download(GET_PIP_URL, getPip)
  }

  console.log('安装 pip…')
  run(pyExe, [getPip, '--no-warn-script-location'], { timeout: 300_000 })

  console.log('安装业务依赖（只需一次，请稍候）…')
  run(pyExe, ['-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'], {
    timeout: 300_000
  })
  run(pyExe, ['-m', 'pip', 'install', '-r', reqFile, '--no-warn-script-location'], {
    timeout: 900_000
  })

  const verify = spawnSync(
    pyExe,
    [
      '-c',
      'import fastapi,uvicorn,loguru,config; print("verify-ok")'
    ],
    {
      cwd: projectRoot,
      windowsHide: true,
      encoding: 'utf8',
      timeout: 30_000,
      env: { ...process.env, PYTHONPATH: projectRoot }
    }
  )
  if (verify.status !== 0) {
    console.warn('依赖校验警告:', verify.stderr || verify.stdout)
  }

  writeFileSync(marker, new Date().toISOString(), 'utf8')
  console.log('完成：', outDir)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
