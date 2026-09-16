/**
 * 整理「发给别人」目录（每次先清空，避免叠加上次的大 zip）
 */
import { existsSync, mkdirSync, writeFileSync, rmSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'
import { spawnSync } from 'child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')
const src = join(root, 'dist-out', 'win-unpacked')
const out = join(root, 'dist-out', '闲鱼管家-发给别人')
const outApp = join(out, '闲鱼管家')

if (!existsSync(src)) {
  console.error('未找到 dist-out/win-unpacked，请先执行：npm run build:win:dir')
  process.exit(1)
}
if (!existsSync(join(src, 'resources', 'project', 'Start.py'))) {
  console.error('缺少 resources/project')
  process.exit(1)
}
if (!existsSync(join(src, 'resources', 'python', 'python.exe'))) {
  console.error('缺少 resources/python（内置运行环境）。请先：npm run prepare:runtime')
  process.exit(1)
}

if (existsSync(out)) {
  rmSync(out, { recursive: true, force: true })
}
mkdirSync(out, { recursive: true })

const readme = `闲鱼管家

【发给别人】
把「闲鱼管家」整个文件夹打成 zip 发送，不要只发 exe。

【对方使用】
解压后双击：闲鱼管家\\XianyuGuanjia.exe

已内置运行环境，对方电脑：
- 不需要安装 Python
- 不需要 pip install
- 不需要开命令行

第一次打开稍等几秒即可扫码。
`

writeFileSync(join(src, '请先读我.txt'), readme, 'utf8')
writeFileSync(join(out, '请先读我.txt'), readme, 'utf8')

const r = spawnSync(
  'robocopy',
  [src, outApp, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/nc', '/ns', '/np'],
  { encoding: 'utf8', windowsHide: true }
)
if ((r.status ?? 1) >= 8) {
  console.error('复制失败', r.stdout || r.stderr)
  process.exit(1)
}
console.log('已生成：', out)
