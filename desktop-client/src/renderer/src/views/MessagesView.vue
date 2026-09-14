<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NAvatar,
  NBadge,
  NButton,
  NDropdown,
  NEmpty,
  NForm,
  NFormItem,
  NIcon,
  NImage,
  NInput,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NList,
  NListItem,
  NModal,
  NSpace,
  NText,
  NThing,
  useMessage,
  type DropdownOption
} from 'naive-ui'
import { CheckmarkOutline, ImageOutline, AttachOutline, EllipsisHorizontal, DownloadOutline } from '@vicons/ionicons5'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import { useChatUnreadStore, unlockChatAudio } from '../stores/chatUnread'
import {
  getChatMessages,
  getChatSessions,
  sendChatMessage,
  syncChatSessions,
  type ChatMessage
} from '../api/chat'
import { apiBase } from '../api/http'

const message = useMessage()
const route = useRoute()
const accountStore = useAccountStore()
const unread = useChatUnreadStore()
const loading = ref(false)
const sessions = ref<ChatMessage[]>([])
const messages = ref<ChatMessage[]>([])
const activeChatId = ref('')
const draft = ref('')
const sending = ref(false)
const msgBox = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const imageInput = ref<HTMLInputElement | null>(null)
/** 引用回复 */
const quoteMsg = ref<ChatMessage | null>(null)
/** 应用内图片放大预览 */
const imgPreviewShow = ref(false)
const imgPreviewUrl = ref('')
/** 消息气泡右键/⋯ 菜单（Electron 下 controlled 更可靠） */
const msgMenuShow = ref(false)
const msgMenuX = ref(0)
const msgMenuY = ref(0)
const msgMenuTarget = ref<ChatMessage | null>(null)
/** 备注弹窗 */
const remarkShow = ref(false)
const remarkDraft = ref('')
const remarkBuyerId = ref('')
/** 备注保存后递增，驱动 displayNick 刷新 */
const remarkTick = ref(0)

const REMARK_KEY = 'xy_chat_remarks'

const activeSession = computed(() =>
  sessions.value.find((s) => {
    if (s.chat_id === activeChatId.value) return true
    return sessionChatIds(s).includes(activeChatId.value)
  })
)
const myAvatar = computed(() => accountStore.activeAccount?.avatar_url || '')
const myNick = computed(() => accountStore.activeAccount?.nickname || '我')

const chatMenuOptions: DropdownOption[] = [
  { label: '查看主页', key: 'profile' },
  { label: '设置备注', key: 'remark' }
]

function sessionChatIds(s?: ChatMessage | null): string[] {
  if (!s) return []
  const extra = s.chat_ids
  const fromExtra = Array.isArray(extra) ? extra.map(String).filter(Boolean) : []
  const primary = s.chat_id ? [String(s.chat_id)] : []
  return [...new Set([...primary, ...fromExtra])]
}

function isRealChatId(id?: string): boolean {
  const c = String(id || '').trim()
  return !!c && c !== '0' && c !== 'null' && c !== 'undefined'
}

function sessionScore(s: ChatMessage): number {
  let score = 0
  if (isRealChatId(s.chat_id)) score += 100
  const content = String(s.content || '').trim()
  if (content && content !== '[会话]' && !content.startsWith('[会话]')) {
    score += Math.min(content.length, 50)
  }
  if (s.content_pic) score += 20
  if (s.buyer_avatar) score += 10
  const nick = String(s.buyer_nick || '')
  if (nick && !['系统', 'system', 'System'].includes(nick)) score += 10
  if (s.item_title || s.item_pic) score += 15
  score += Math.min(Number(s.ts || 0) / 1e12, 5)
  return score
}

/** 同一 buyer_id 合并为一条会话；优先保留真实 chat_id 且内容更丰富的那条 */
function mergeSessionsByBuyer(list: ChatMessage[]): ChatMessage[] {
  const map = new Map<string, ChatMessage>()
  const orphans: ChatMessage[] = []

  for (const raw of list) {
    const bid = String(raw.buyer_id || '').trim()
    if (!bid) {
      orphans.push({
        ...raw,
        chat_ids: raw.chat_id ? [String(raw.chat_id)] : []
      })
      continue
    }
    const existing = map.get(bid)
    if (!existing) {
      map.set(bid, {
        ...raw,
        chat_ids: raw.chat_id ? [String(raw.chat_id)] : []
      })
      continue
    }
    const ids = new Set<string>([
      ...sessionChatIds(existing),
      ...(raw.chat_id ? [String(raw.chat_id)] : [])
    ])
    const preferNew = sessionScore(raw) > sessionScore(existing)
    const base: ChatMessage = preferNew ? { ...raw } : { ...existing }
    const other = preferNew ? existing : raw
    if (!base.buyer_avatar && other.buyer_avatar) base.buyer_avatar = other.buyer_avatar
    if (!base.buyer_nick && other.buyer_nick) base.buyer_nick = other.buyer_nick
    if (!base.item_title && other.item_title) base.item_title = other.item_title
    if (!base.item_pic && other.item_pic) base.item_pic = other.item_pic
    if (!base.item_id && other.item_id) base.item_id = other.item_id
    if ((other.ts || 0) > (base.ts || 0)) {
      base.content = other.content
      base.content_pic = other.content_pic
      base.ts = other.ts
    }
    if (!isRealChatId(String(base.chat_id || '')) && isRealChatId(String(other.chat_id || ''))) {
      base.chat_id = other.chat_id
    } else if (preferNew && isRealChatId(String(raw.chat_id || ''))) {
      base.chat_id = raw.chat_id
    } else if (!preferNew && isRealChatId(String(existing.chat_id || ''))) {
      base.chat_id = existing.chat_id
    }
    if (base.chat_id) ids.add(String(base.chat_id))
    base.chat_ids = [...ids]
    map.set(bid, base)
  }

  const merged = [...map.values(), ...orphans]
  merged.sort((a, b) => (b.ts || 0) - (a.ts || 0))
  return merged
}

function sessionUnreadTotal(s: ChatMessage): number {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) return 0
  return sessionChatIds(s).reduce((sum, cid) => sum + unread.sessionUnread(cookieId, cid), 0)
}

function resolveMediaUrl(url?: string): string {
  const u = String(url || '')
  if (!u) return ''
  if (u.startsWith('data:') || /^https?:\/\//i.test(u)) return u
  // Electron / 打包环境下相对路径不稳定，静态资源直连后端
  const base = apiBase() || 'http://127.0.0.1:8080'
  if (u.startsWith('/')) return `${base}${u}`
  return u
}

function mediaSrc(m: ChatMessage): string {
  return resolveMediaUrl(String(m.content_pic || m.content || ''))
}

function loadRemarks(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(REMARK_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveRemark(buyerId: string, remark: string): void {
  const map = loadRemarks()
  if (remark) map[buyerId] = remark
  else delete map[buyerId]
  localStorage.setItem(REMARK_KEY, JSON.stringify(map))
}

function displayNick(s?: ChatMessage | null): string {
  void remarkTick.value
  if (!s) return ''
  const bid = String(s.buyer_id || '')
  const remarks = loadRemarks()
  const nick = String(s.buyer_nick || '').trim()
  // 「系统」是订单状态推送误写的昵称，不当作会话名展示
  const safeNick = nick && !['系统', 'system', 'System'].includes(nick) ? nick : ''
  return remarks[bid] || safeNick || bid || s.chat_id || ''
}

function isOutRead(msg: ChatMessage, idx: number): boolean {
  if (msg.direction !== 'out') return false
  return messages.value.slice(idx + 1).some((m) => m.direction === 'in')
}

function formatTime(ts?: number): string {
  if (!ts) return ''
  const t = ts > 1e12 ? ts : ts * 1000
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}

function scrollToBottom(): void {
  void nextTick(() => {
    const el = msgBox.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function applyRouteQuery(): boolean {
  const q = route.query
  const buyerId = String(q.buyerId || '')
  const sellerId = String(q.sellerId || '')
  const itemId = String(q.itemId || '')
  const chatId = String(q.chatId || '')
  if (!sessions.value.length) return false
  let match =
    (chatId &&
      sessions.value.find((s) => s.chat_id === chatId || sessionChatIds(s).includes(chatId))) ||
    (buyerId && sessions.value.find((s) => String(s.buyer_id) === buyerId)) ||
    (sellerId && sessions.value.find((s) => String(s.buyer_id) === sellerId)) ||
    (itemId && sessions.value.find((s) => String(s.item_id) === itemId))
  if (match) {
    activeChatId.value = match.chat_id
    return true
  }
  if (buyerId || sellerId || itemId || chatId) {
    message.warning('未找到对应会话，请先「同步会话」或确认对方曾聊过天')
  }
  return false
}

async function loadSessions(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    sessions.value = []
    messages.value = []
    activeChatId.value = ''
    return
  }
  loading.value = true
  try {
    sessions.value = mergeSessionsByBuyer(await getChatSessions(cookieId))
    const fromQuery = applyRouteQuery()
    if (!fromQuery && !sessions.value.some((s) => sessionChatIds(s).includes(activeChatId.value))) {
      activeChatId.value = sessions.value[0]?.chat_id || ''
    }
    if (activeChatId.value) await loadMessages(true)
    else messages.value = []
  } catch (e: any) {
    message.error(e?.message || '加载会话失败')
  } finally {
    loading.value = false
  }
}

function dedupeMessages(list: ChatMessage[]): ChatMessage[] {
  const sorted = [...list].sort((a, b) => (a.ts || 0) - (b.ts || 0))
  const seenIds = new Set<string>()
  const out: ChatMessage[] = []
  const WINDOW_MS = 15000
  for (const m of sorted) {
    if (m.id != null) {
      const idKey = `id:${m.id}`
      if (seenIds.has(idKey)) continue
      seenIds.add(idKey)
    }
    const contentKey = `${m.direction}|${String(m.content || '')}|${String(m.content_pic || '')}`
    const ts = Number(m.ts) || 0
    const dup = out.find((prev) => {
      const prevKey = `${prev.direction}|${String(prev.content || '')}|${String(prev.content_pic || '')}`
      if (prevKey !== contentKey) return false
      const prevTs = Number(prev.ts) || 0
      return Math.abs(prevTs - ts) <= WINDOW_MS
    })
    if (dup) {
      // 保留带 id / 更完整 pic 的那条
      if ((m.id != null && dup.id == null) || (!dup.content_pic && m.content_pic)) {
        const idx = out.indexOf(dup)
        out[idx] = { ...dup, ...m, content_pic: m.content_pic || dup.content_pic }
      }
      continue
    }
    out.push(m)
  }
  return out
}

async function loadMessages(markRead = false): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId || !activeChatId.value) return
  const sess = activeSession.value
  const chatIds = sess ? sessionChatIds(sess) : [activeChatId.value]
  try {
    const batches = await Promise.all(
      chatIds.map((cid) => getChatMessages(cookieId, cid).catch(() => [] as ChatMessage[]))
    )
    messages.value = dedupeMessages(batches.flat())
    if (markRead) {
      for (const cid of chatIds) unread.clearSession(cookieId, cid)
    }
    scrollToBottom()
  } catch (e: any) {
    message.error(e?.message || '加载消息失败')
  }
}

async function onSync(silent = false): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) return
  try {
    await syncChatSessions(cookieId)
    if (!silent) message.success('已同步会话')
    await loadSessions()
  } catch (e: any) {
    if (!silent) message.error(e?.message || '同步失败')
  }
}

function markAllRead(): void {
  unread.clearAll()
  message.success('已全部标为已读')
}

function openItemPage(): void {
  const s = activeSession.value
  if (!s) return
  const id = s.item_id
  const url =
    (s as any).item_url ||
    (id ? `https://www.goofish.com/item?id=${id}` : '')
  if (url) window.open(String(url), '_blank')
}

function onChatMenu(key: string | number): void {
  const s = activeSession.value
  if (!s) return
  const buyerId = String(s.buyer_id || '')
  if (key === 'profile') {
    if (buyerId) window.open(`https://www.goofish.com/personal?userId=${buyerId}`, '_blank')
    else message.warning('无买家 ID')
  } else if (key === 'remark') {
    remarkBuyerId.value = buyerId
    remarkDraft.value = loadRemarks()[buyerId] || String(s.buyer_nick || '')
    remarkShow.value = true
  }
}

function confirmRemark(): void {
  const buyerId = remarkBuyerId.value
  if (!buyerId) {
    remarkShow.value = false
    return
  }
  const name = remarkDraft.value.trim()
  saveRemark(buyerId, name)
  remarkTick.value += 1
  remarkShow.value = false
  message.success(name ? '备注已保存' : '已清除备注')
}

async function onSend(extra?: { text?: string; pic?: string }): Promise<void> {
  if (sending.value) return
  const cookieId = accountStore.activeCookieId
  const sess = activeSession.value
  let text = (extra?.text ?? draft.value).trim()
  if (!cookieId || !sess || (!text && !extra?.pic)) return
  if (!sess.chat_id) {
    message.warning('当前会话缺少 chat_id，请等对方先发一条消息后再试，或点「同步会话」')
    return
  }
  if (quoteMsg.value && text && !extra?.pic) {
    const q = quoteMsg.value
    const qNick = q.direction === 'out' ? myNick.value : displayNick(activeSession.value) || '对方'
    let qBody = String(q.content || '[消息]').slice(0, 120)
    const qPic = String(q.content_pic || '').trim()
    if (isImageMsg(q)) {
      // 把图片 URL 嵌进引用标记，便于气泡里还原缩略图
      qBody = qPic ? `[图片]|${qPic}` : '[图片]'
    }
    text = `「引用 ${qNick}：${qBody}」\n${text}`
  }
  sending.value = true
  const sendToken = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const optimistic: ChatMessage = {
    cookie_id: cookieId,
    chat_id: sess.chat_id,
    buyer_id: String(sess.buyer_id || ''),
    content: text || (extra?.pic ? '[图片]' : ''),
    content_pic: extra?.pic || '',
    direction: 'out',
    ts: Date.now(),
    // 临时标记，方便替换；不会入库
    id: `local-${sendToken}` as any
  }
  messages.value = [...messages.value, optimistic]
  scrollToBottom()
  try {
    const res = await sendChatMessage({
      cookie_id: cookieId,
      chat_id: sess.chat_id,
      to_user_id: String(sess.buyer_id || ''),
      message: text || (extra?.pic ? '[图片]' : ''),
      content_pic: extra?.pic
    })
    const data = (res as any)?.data
    // WS 可能已刷新列表，乐观消息不一定还在：只按内容去重合并，禁止再插一条
    const merged: ChatMessage = {
      cookie_id: cookieId,
      chat_id: sess.chat_id,
      buyer_id: String(sess.buyer_id || ''),
      content: String(data?.content || optimistic.content || ''),
      content_pic: String(data?.content_pic || optimistic.content_pic || ''),
      direction: 'out',
      ts: Number(data?.ts) || optimistic.ts
    }
    const withoutLocal = messages.value.filter(
      (m) => m !== optimistic && String(m.id || '') !== String(optimistic.id)
    )
    messages.value = dedupeMessages([...withoutLocal, merged])
    if (!extra) {
      draft.value = ''
      quoteMsg.value = null
    }
    scrollToBottom()
  } catch (e: any) {
    messages.value = messages.value.filter(
      (m) => m !== optimistic && String(m.id || '') !== String(optimistic.id)
    )
    message.error(e?.message || '发送失败')
  } finally {
    sending.value = false
  }
}

function setQuote(m: ChatMessage): void {
  quoteMsg.value = m
  message.info('已引用，输入内容后发送')
}

function clearQuote(): void {
  quoteMsg.value = null
}

function parseQuoteContent(content: string): { quote?: string; quotePic?: string; body: string } {
  const c = String(content || '')
  const m = c.match(/^「引用\s*([^：:]+)[：:]([\s\S]*?)」\n([\s\S]*)$/)
  if (m) {
    const nick = m[1]
    let qRaw = String(m[2] || '').trim()
    let quotePic = ''
    // 「引用 xx：[图片]|https://...」或纯 URL
    const picMark = qRaw.match(/^\[图片\]\s*\|\s*(.+)$/i)
    if (picMark) {
      quotePic = picMark[1].trim()
      qRaw = '[图片]'
    } else if (/^https?:\/\//i.test(qRaw) && /\.(png|jpe?g|gif|webp|bmp)(\?|$)/i.test(qRaw)) {
      quotePic = qRaw
      qRaw = '[图片]'
    } else if (qRaw.includes('[图片]|')) {
      const parts = qRaw.split('[图片]|')
      if (parts[1]) {
        quotePic = parts[1].trim()
        qRaw = (parts[0] + '[图片]').trim() || '[图片]'
      }
    }
    return { quote: `${nick}：${qRaw}`, quotePic, body: m[3] }
  }
  return { body: c }
}

function msgContextOptions(m: ChatMessage): DropdownOption[] {
  const opts: DropdownOption[] = [
    { label: '引用 / 回复', key: 'quote' },
    { label: '复制文本', key: 'copy' }
  ]
  if (isImageMsg(m)) {
    opts.push(
      { label: '复制图片', key: 'copy-image' },
      { label: '放大图片', key: 'open-image' }
    )
  }
  return opts
}

function isSystemMsg(m: ChatMessage): boolean {
  // 图片/文件/视频绝不当成系统消息（否则 [图片] 会居中显示成灰字）
  if (isImageMsg(m) || isVideoMsg(m) || isFileMsg(m)) return false
  const c = String(m.content || '').trim()
  if (!c) return false
  // 媒体占位文案
  if (c === '[图片]' || c === '[视频]' || c.startsWith('[文件]')) return false
  if (m.buyer_nick === '系统') return true
  const sysExact = new Set([
    '[我已拍下，待付款]',
    '[你关闭了订单，钱款已原路退返]',
    '[买家确认收货，交易成功]',
    '[你已确认收货，交易成功]',
    '[你已发货]',
    '[交易成功，等待卖家发货]',
    '[等待买家付款]',
    '[交易关闭]',
    '[我已发货，请查看发货凭证]',
    '[我完成了评价]',
    '已发货',
    '买家确认收货，交易成功',
    '我完成了评价',
    '快给ta一个评价吧~',
    '快给ta一个评价吧～',
    '卖家人不错？送Ta闲鱼小红花'
  ])
  if (sysExact.has(c)) return true
  return (
    (c.includes('交易成功') && !c.includes('引用')) ||
    c.includes('等待买家付款') ||
    c.includes('交易关闭') ||
    c === '已发货'
  )
}

function isImageMsg(m: ChatMessage): boolean {
  const pic = String(m.content_pic || '')
  const content = String(m.content || '').trim()
  if (isVideoMsg(m)) return false
  if (pic.startsWith('data:image')) return true
  if (pic && /\.(png|jpe?g|gif|webp|bmp)(\?|$)/i.test(pic)) return true
  if (
    pic &&
    (pic.includes('/static/uploads/images') ||
      pic.includes('alicdn') ||
      pic.includes('img.') ||
      pic.includes('goofish') ||
      pic.includes('stream-upload'))
  ) {
    return !/\.(pdf|docx?|xlsx?|zip|rar|7z|txt|apk|exe|dmg)(\?|$)/i.test(pic)
  }
  // 有图地址或明确是图片占位且带 pic
  if ((content === '[图片]' || content.includes('[图片]')) && pic) return true
  // 仅有 [图片] 占位时也按图片气泡渲染（避免掉进系统居中样式）
  if (content === '[图片]') return true
  if (/^https?:\/\//i.test(content) && /\.(png|jpe?g|gif|webp|bmp)(\?|$)/i.test(content)) return true
  return /\.(png|jpe?g|gif|webp|bmp)(\?|$)/i.test(content)
}

async function copyImageToClipboard(m: ChatMessage): Promise<void> {
  const url = mediaSrc(m)
  if (!url) {
    message.warning('无图片地址')
    return
  }
  try {
    // 先尝试转成 PNG，避免 Electron 对 jpeg ClipboardItem 支持差而退化成复制路径
    const res = await fetch(url)
    const srcBlob = await res.blob()
    const pngBlob = await blobToPngBlob(srcBlob)
    const api = (window as any).api || (window as any).electronAPI
    if (api?.copyImageFromUrl) {
      const r = await api.copyImageFromUrl(url)
      if (r?.ok) {
        message.success('图片已复制')
        return
      }
    }
    if (typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
      await navigator.clipboard.write([
        new ClipboardItem({
          'image/png': pngBlob
        })
      ])
      message.success('图片已复制')
      return
    }
  } catch (e) {
    console.warn('copy image failed', e)
  }
  message.error('复制图片失败（可改用右键保存）')
}

function blobToPngBlob(blob: Blob): Promise<Blob> {
  return new Promise((resolve, reject) => {
    if (blob.type === 'image/png') {
      resolve(blob)
      return
    }
    const img = new Image()
    img.crossOrigin = 'anonymous'
    const objUrl = URL.createObjectURL(blob)
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = img.naturalWidth || img.width
        canvas.height = img.naturalHeight || img.height
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('no canvas'))
          return
        }
        ctx.drawImage(img, 0, 0)
        canvas.toBlob(
          (b) => {
            URL.revokeObjectURL(objUrl)
            if (b) resolve(b)
            else reject(new Error('toBlob failed'))
          },
          'image/png'
        )
      } catch (err) {
        URL.revokeObjectURL(objUrl)
        reject(err)
      }
    }
    img.onerror = () => {
      URL.revokeObjectURL(objUrl)
      reject(new Error('image load failed'))
    }
    img.src = objUrl
  })
}

function openImagePreview(m: ChatMessage): void {
  const url = mediaSrc(m)
  if (!url) {
    message.warning('无图片地址')
    return
  }
  imgPreviewUrl.value = url
  imgPreviewShow.value = true
}

function openImageUrl(url: string): void {
  const u = resolveMediaUrl(url)
  if (!u) return
  imgPreviewUrl.value = u
  imgPreviewShow.value = true
}

async function onMsgContext(key: string | number, m: ChatMessage): Promise<void> {
  if (key === 'quote') setQuote(m)
  else if (key === 'copy') {
    try {
      const parsed = parseQuoteContent(String(m.content || ''))
      const text = (parsed.body || String(m.content || '')).trim()
      await navigator.clipboard.writeText(text)
      message.success('已复制')
    } catch {
      message.error('复制失败')
    }
  } else if (key === 'copy-image') {
    await copyImageToClipboard(m)
  } else if (key === 'open-image') {
    openImagePreview(m)
  }
}

function onBubbleContext(e: MouseEvent, m: ChatMessage): void {
  e.preventDefault()
  e.stopPropagation()
  msgMenuTarget.value = m
  msgMenuX.value = e.clientX
  msgMenuY.value = e.clientY
  // Electron 下 manual 下拉需要先关再开，否则第二次右键无反应
  msgMenuShow.value = false
  void nextTick(() => {
    msgMenuShow.value = true
  })
}

function onBubbleMenuBtn(e: MouseEvent, m: ChatMessage): void {
  e.preventDefault()
  e.stopPropagation()
  msgMenuTarget.value = m
  const el = e.currentTarget as HTMLElement | null
  if (el) {
    const rect = el.getBoundingClientRect()
    msgMenuX.value = Math.round(rect.left)
    msgMenuY.value = Math.round(rect.bottom + 2)
  } else {
    msgMenuX.value = e.clientX
    msgMenuY.value = e.clientY
  }
  msgMenuShow.value = false
  void nextTick(() => {
    msgMenuShow.value = true
  })
}

async function onMsgMenuSelect(key: string | number): Promise<void> {
  const m = msgMenuTarget.value
  msgMenuShow.value = false
  if (!m) return
  await onMsgContext(key, m)
}

function onComposerKeydown(e: KeyboardEvent): void {
  // 中文输入法组字中不触发发送
  if (e.isComposing || (e as KeyboardEvent & { keyCode?: number }).keyCode === 229) return
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault()
    void onSend()
  }
}

function selectChat(chatId: string): void {
  activeChatId.value = chatId
  syncActiveChatKey()
  void loadMessages(true)
}

function onWsMessage(ev: Event): void {
  const data = (ev as CustomEvent).detail || {}
  const isSync = data.direction === 'sync' || data.source === 'session_sync'
  const cookieId = accountStore.activeCookieId
  // 未读只由全局 WS + pushIncoming 去重计算，消息页只刷新 UI
  if (!cookieId || data.cookie_id !== cookieId) return
  // 自己正在发送时，跳过整表刷新，避免与乐观消息打架导致双条
  if (sending.value && data.direction === 'out') {
    void loadSessions()
    return
  }
  void (async () => {
    await loadSessions()
    const sess = activeSession.value
    const ids = sess ? sessionChatIds(sess) : []
    const incomingChat = String(data.chat_id || '').split('@')[0]
    const activeIds = new Set(ids.map((x) => String(x).split('@')[0]))
    if (
      incomingChat &&
      (incomingChat === String(activeChatId.value).split('@')[0] || activeIds.has(incomingChat)) &&
      !isSync
    ) {
      await loadMessages(true)
    }
  })()
}

function syncActiveChatKey(): void {
  const cid = accountStore.activeCookieId || ''
  const sess = sessions.value.find(
    (s) => s.chat_id === activeChatId.value || sessionChatIds(s).includes(activeChatId.value)
  )
  const ids = sess ? sessionChatIds(sess) : activeChatId.value ? [activeChatId.value] : []
  ;(window as any).__xyActiveChatKey = ids[0] && cid ? `${cid}::${ids[0]}` : ''
  ;(window as any).__xyActiveChatKeys = cid ? ids.map((id) => `${cid}::${id}`) : []
}

function pickImage(): void {
  imageInput.value?.click()
}
function pickFile(): void {
  fileInput.value?.click()
}

async function onFilePicked(ev: Event, kind: 'image' | 'file'): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    const url = String(reader.result || '')
    if (kind === 'image') void onSend({ text: '', pic: url })
    else void onSend({ text: `[文件] ${file.name}`, pic: url })
  }
  reader.readAsDataURL(file)
}

function onPaste(ev: ClipboardEvent): void {
  const items = ev.clipboardData?.items
  if (!items) return
  for (const it of Array.from(items)) {
    if (it.type.startsWith('image/')) {
      ev.preventDefault()
      const file = it.getAsFile()
      if (!file) return
      const reader = new FileReader()
      reader.onload = () => {
        void onSend({ text: '', pic: String(reader.result || '') })
      }
      reader.readAsDataURL(file)
      return
    }
  }
}

function isVideoMsg(m: ChatMessage): boolean {
  return /\.(mp4|webm|mov)(\?|$)/i.test(String(m.content_pic || m.content || ''))
}

function isFileMsg(m: ChatMessage): boolean {
  const c = String(m.content || '')
  if (c.startsWith('[文件]')) return true
  const pic = String(m.content_pic || '')
  if (!pic) return false
  if (/\.(png|jpe?g|gif|webp|bmp|mp4|webm|mov)(\?|$)/i.test(pic)) return false
  return /\.(pdf|docx?|xlsx?|zip|rar|7z|txt|apk|exe|dmg)(\?|$)/i.test(pic)
}

async function saveMediaAs(m: ChatMessage): Promise<void> {
  const url = mediaSrc(m)
  if (!url) {
    message.warning('没有可下载的文件地址')
    return
  }
  const label = fileLabel(m) || (isImageMsg(m) ? 'image.jpg' : 'file.bin')
  try {
    const api = (window as any).api || (window as any).electronAPI
    if (api?.saveRemoteFile) {
      const r = await api.saveRemoteFile(url, label)
      if (r?.ok) {
        message.success(r.path ? `已保存到 ${r.path}` : '已保存')
        return
      }
      if (r && r.ok === false && !r.path) {
        // 用户取消
        return
      }
    }
  } catch {
    /* fallthrough */
  }
  // 浏览器兜底：新开下载
  const a = document.createElement('a')
  a.href = url
  a.target = '_blank'
  a.rel = 'noopener'
  a.download = label
  document.body.appendChild(a)
  a.click()
  a.remove()
}

function fileDownloadUrl(m: ChatMessage): string {
  return resolveMediaUrl(String(m.content_pic || m.content || ''))
}

function fileLabel(m: ChatMessage): string {
  const c = String(m.content || '')
  if (c.startsWith('[文件]')) return c.replace(/^\[文件\]\s*/, '') || '附件'
  const url = String(m.content_pic || m.content || '')
  const name = url.split('/').pop()?.split('?')[0]
  return name || '附件下载'
}

watch(messages, () => scrollToBottom())
watch(
  () => route.query,
  () => {
    if (sessions.value.length) {
      if (applyRouteQuery()) void loadMessages(true)
    }
  }
)

onMounted(() => {
  void unlockChatAudio()
  document.addEventListener('click', () => void unlockChatAudio(), { once: true })
  syncActiveChatKey()
  void loadSessions().then(() => void onSync(true))
  window.addEventListener('xy-chat-message', onWsMessage)
  window.addEventListener('xy-sessions-synced', onSessionsSynced)
})

onBeforeUnmount(() => {
  ;(window as any).__xyActiveChatKey = ''
  ;(window as any).__xyActiveChatKeys = []
  window.removeEventListener('xy-chat-message', onWsMessage)
  window.removeEventListener('xy-sessions-synced', onSessionsSynced)
})

function onSessionsSynced(): void {
  void loadSessions()
}

watch(activeChatId, () => syncActiveChatKey())
watch(
  () => accountStore.activeCookieId,
  () => syncActiveChatKey()
)
</script>

<template>
  <div class="messages-page">
    <div class="messages-top">
      <n-text strong style="font-size: 16px">消息</n-text>
      <AccountTabs @change="loadSessions" />
      <n-space style="margin-bottom: 4px" align="center">
        <n-button size="small" secondary :loading="loading" @click="onSync(false)">同步会话</n-button>
        <n-button size="small" quaternary @click="markAllRead">全部已读</n-button>
        <n-text depth="3" style="font-size: 12px">会话自动同步中 · 新消息红点 + 提示音</n-text>
      </n-space>
    </div>

    <n-layout has-sider class="messages-body">
      <n-layout-sider bordered :width="280" :native-scrollbar="false" content-style="padding: 0">
        <n-list hoverable clickable>
          <n-list-item
            v-for="s in sessions"
            :key="s.chat_id + ':' + String(s.buyer_id || '')"
            :class="{ active: s.chat_id === activeChatId || sessionChatIds(s).includes(activeChatId) }"
            @click="selectChat(s.chat_id)"
          >
            <n-badge
              :value="sessionUnreadTotal(s)"
              :max="99"
              :show="sessionUnreadTotal(s) > 0"
            >
              <n-thing>
                <template #avatar>
                  <n-avatar round :size="40" :src="s.buyer_avatar" />
                </template>
                <template #header>
                  <n-text strong>{{ displayNick(s) }}</n-text>
                </template>
                <template #description>
                  <n-text depth="3" style="font-size: 12px" class="ellipsis">{{ s.content }}</n-text>
                </template>
              </n-thing>
            </n-badge>
          </n-list-item>
        </n-list>
        <n-empty v-if="!sessions.length" description="暂无会话" style="margin-top: 40px" />
      </n-layout-sider>

      <n-layout-content content-style="display:flex;flex-direction:column;height:100%;padding:12px;min-height:0;overflow:hidden">
        <div v-if="activeSession" class="chat-head">
          <n-space align="center">
            <n-avatar round :size="32" :src="activeSession.buyer_avatar" />
            <n-text strong>{{ displayNick(activeSession) }}</n-text>
            <n-dropdown trigger="click" :options="chatMenuOptions" @select="onChatMenu">
              <n-button quaternary circle size="small">
                <template #icon><n-icon :component="EllipsisHorizontal" /></template>
              </n-button>
            </n-dropdown>
          </n-space>
          <div
            v-if="activeSession.item_title || activeSession.item_pic"
            class="item-float"
            role="button"
            @click="openItemPage"
          >
            <n-image
              v-if="activeSession.item_pic"
              :src="resolveMediaUrl(String(activeSession.item_pic))"
              width="36"
              height="36"
              object-fit="cover"
              preview-disabled
            />
            <n-text depth="3" style="font-size: 12px; max-width: 160px" class="ellipsis">{{
              activeSession.item_title
            }}</n-text>
          </div>
        </div>

        <div ref="msgBox" class="msg-list">
          <div
            v-for="(m, idx) in messages"
            :key="m.id || m.ts + String(m.content) + String(m.content_pic || '')"
            class="msg-row"
            :class="isSystemMsg(m) ? 'sys' : m.direction === 'out' ? 'out' : 'in'"
          >
            <template v-if="isSystemMsg(m)">
              <div class="sys-bubble" @contextmenu.prevent="onBubbleContext($event, m)">
                {{ m.content }}
              </div>
            </template>
            <template v-else>
            <n-avatar
              round
              :size="32"
              :src="m.direction === 'out' ? myAvatar : m.buyer_avatar || activeSession?.buyer_avatar"
            />
            <div class="bubble-wrap">
              <div class="meta">
                <n-text style="font-size: 12px">
                  {{ m.direction === 'out' ? myNick : displayNick(activeSession) || m.buyer_nick || '买家' }}
                </n-text>
                <n-text depth="3" style="font-size: 11px; margin-left: 8px">{{ formatTime(m.ts) }}</n-text>
              </div>
              <div
                class="bubble"
                :class="m.direction === 'out' ? 'out' : 'in'"
                @contextmenu.prevent="onBubbleContext($event, m)"
              >
                <n-button
                  class="bubble-menu-btn"
                  size="tiny"
                  quaternary
                  circle
                  title="更多"
                  @click="onBubbleMenuBtn($event, m)"
                >
                  <template #icon>
                    <n-icon :component="EllipsisHorizontal" :size="14" />
                  </template>
                </n-button>
                <template v-if="!isImageMsg(m) && !isVideoMsg(m) && !isFileMsg(m)">
                  <div v-if="parseQuoteContent(String(m.content || '')).quote" class="quote-box">
                    <div class="quote-text">{{ parseQuoteContent(String(m.content || '')).quote }}</div>
                    <img
                      v-if="parseQuoteContent(String(m.content || '')).quotePic"
                      class="quote-img"
                      :src="resolveMediaUrl(String(parseQuoteContent(String(m.content || '')).quotePic || ''))"
                      alt="引用图片"
                      title="点击放大"
                      @click.stop="openImageUrl(String(parseQuoteContent(String(m.content || '')).quotePic || ''))"
                    />
                  </div>
                  <n-text class="bubble-text">{{ parseQuoteContent(String(m.content || '')).body }}</n-text>
                </template>
                <div v-else-if="isImageMsg(m)" class="media-file" :class="m.direction === 'out' ? 'out' : 'in'">
                  <img
                    v-if="mediaSrc(m)"
                    class="msg-img clickable"
                    :src="mediaSrc(m)"
                    alt="图片"
                    loading="lazy"
                    title="点击放大"
                    @click.stop="openImagePreview(m)"
                    @error="($event.target as HTMLImageElement).style.display='none'"
                  />
                  <div v-else class="img-placeholder">图片加载中…</div>
                  <n-button
                    v-if="mediaSrc(m)"
                    size="tiny"
                    quaternary
                    circle
                    title="保存图片"
                    @click.stop="saveMediaAs(m)"
                  >
                    <template #icon>
                      <n-icon :component="DownloadOutline" />
                    </template>
                  </n-button>
                </div>
                <div v-else-if="isVideoMsg(m)" class="media-file">
                  <video :src="mediaSrc(m)" controls style="max-width: 220px" />
                  <n-button size="tiny" quaternary circle title="下载视频" @click="saveMediaAs(m)">
                    <template #icon>
                      <n-icon :component="DownloadOutline" />
                    </template>
                  </n-button>
                </div>
                <div v-else-if="isFileMsg(m)" class="file-card">
                  <n-text>{{ fileLabel(m) }}</n-text>
                  <n-button size="tiny" type="primary" secondary @click="saveMediaAs(m)">下载文件</n-button>
                </div>
                <div v-if="m.direction === 'out'" class="reads">
                  <n-icon
                    :component="CheckmarkOutline"
                    :color="isOutRead(m, idx) ? '#2080f0' : '#999'"
                    :size="14"
                  />
                  <n-icon
                    v-if="isOutRead(m, idx)"
                    :component="CheckmarkOutline"
                    color="#2080f0"
                    :size="14"
                    style="margin-left: -6px"
                  />
                </div>
              </div>
            </div>
            </template>
          </div>
          <n-empty v-if="!messages.length" description="选择左侧会话查看消息" />
        </div>

        <n-dropdown
          placement="bottom-start"
          trigger="manual"
          :x="msgMenuX"
          :y="msgMenuY"
          :show="msgMenuShow"
          :options="msgMenuTarget ? msgContextOptions(msgMenuTarget) : []"
          :z-index="4000"
          @select="onMsgMenuSelect"
          @clickoutside="msgMenuShow = false"
        />

        <div v-if="quoteMsg" class="quote-bar">
          <img
            v-if="isImageMsg(quoteMsg) && mediaSrc(quoteMsg)"
            class="quote-bar-img"
            :src="mediaSrc(quoteMsg)"
            alt=""
          />
          <div class="quote-bar-text">
            引用：{{
              isImageMsg(quoteMsg) ? '[图片]' : String(quoteMsg.content || '').slice(0, 60)
            }}
          </div>
          <n-button size="tiny" quaternary @click="clearQuote">取消</n-button>
        </div>

        <div class="composer">
          <n-button quaternary circle @click="pickImage">
            <template #icon><n-icon :component="ImageOutline" /></template>
          </n-button>
          <n-button quaternary circle @click="pickFile">
            <template #icon><n-icon :component="AttachOutline" /></template>
          </n-button>
          <n-input
            v-model:value="draft"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 3 }"
            placeholder="输入消息…（Enter 发送，Shift+Enter 换行，可粘贴截图）"
            class="composer-input"
            @paste="onPaste"
            @keydown="onComposerKeydown"
          />
          <n-button type="primary" :loading="sending" :disabled="!activeChatId" @click="onSend()"
            >发送</n-button
          >
        </div>
        <input ref="imageInput" type="file" accept="image/*" hidden @change="onFilePicked($event, 'image')" />
        <input ref="fileInput" type="file" hidden @change="onFilePicked($event, 'file')" />

        <n-modal
          v-model:show="imgPreviewShow"
          preset="card"
          title="图片预览"
          style="width: min(860px, 92vw)"
          :bordered="false"
          display-directive="show"
        >
          <div class="img-preview-wrap">
            <img v-if="imgPreviewUrl" :src="imgPreviewUrl" alt="预览" class="img-preview-full" />
          </div>
          <n-space justify="end" style="margin-top: 12px">
            <n-button @click="imgPreviewShow = false">关闭</n-button>
          </n-space>
        </n-modal>
      </n-layout-content>
    </n-layout>

    <n-modal
      v-model:show="remarkShow"
      preset="card"
      title="设置备注"
      style="width: 400px"
      :mask-closable="false"
    >
      <n-form>
        <n-form-item label="备注名">
          <n-input
            v-model:value="remarkDraft"
            placeholder="输入备注名，清空则清除备注"
            maxlength="40"
            show-count
            @keydown.enter.prevent="confirmRemark"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="remarkShow = false">取消</n-button>
          <n-button type="primary" @click="confirmRemark">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.messages-page {
  height: calc(100vh - 52px - 40px - 32px);
  max-height: calc(100vh - 52px - 40px - 32px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.messages-top {
  flex-shrink: 0;
}
.messages-body {
  flex: 1;
  min-height: 0;
  background: transparent;
  overflow: hidden;
}
.active {
  background: rgba(24, 160, 88, 0.1);
}
.ellipsis {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--app-border);
  flex-shrink: 0;
}
.item-float {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 220px;
  cursor: pointer;
}
.msg-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  margin-bottom: 8px;
  padding-right: 4px;
}
.msg-row {
  display: flex;
  gap: 8px;
  margin: 12px 0;
  clear: both;
}
.msg-row.out {
  flex-direction: row-reverse;
}
.msg-row.sys {
  justify-content: center;
}
.sys-bubble {
  max-width: 80%;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(128, 128, 128, 0.12);
  color: #888;
  font-size: 12px;
  text-align: center;
  cursor: context-menu;
}
.bubble-wrap {
  max-width: 70%;
}
.meta {
  margin-bottom: 4px;
}
.msg-row.out .meta {
  text-align: right;
}
.bubble {
  padding: 8px 12px;
  border-radius: 8px;
  position: relative;
  user-select: text;
  -webkit-user-select: text;
  cursor: context-menu;
  white-space: pre-wrap;
  word-break: break-word;
}
.bubble-menu-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  opacity: 0.45;
  transition: opacity 0.15s;
  z-index: 2;
}
.bubble:hover .bubble-menu-btn {
  opacity: 1;
}
.msg-row.out .bubble-menu-btn {
  right: auto;
  left: 2px;
}
.bubble.in {
  background: var(--msg-in-bg);
}
.bubble.out {
  background: var(--msg-out-bg);
}
.bubble-text {
  user-select: text;
  -webkit-user-select: text;
  white-space: pre-wrap;
  word-break: break-word;
}
.reads {
  display: flex;
  justify-content: end;
  margin-top: 2px;
}
.composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  width: 100%;
  flex-shrink: 0;
}
.composer-input {
  flex: 1;
  min-width: 0;
  width: 100%;
}
.quote-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(32, 128, 240, 0.08);
  border-left: 3px solid #2080f0;
  flex-shrink: 0;
}
.quote-bar-text {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quote-box {
  font-size: 12px;
  opacity: 0.9;
  padding: 4px 6px;
  margin-bottom: 6px;
  border-left: 2px solid rgba(0, 0, 0, 0.2);
  background: rgba(0, 0, 0, 0.04);
  border-radius: 2px;
  white-space: pre-wrap;
  word-break: break-word;
}
.quote-text {
  margin-bottom: 4px;
}
.quote-img {
  max-width: 120px;
  max-height: 120px;
  border-radius: 4px;
  display: block;
  cursor: zoom-in;
  object-fit: cover;
}
.quote-bar-img {
  width: 36px;
  height: 36px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
}
.msg-img {
  max-width: 200px;
  max-height: 260px;
  border-radius: 6px;
  display: block;
  object-fit: contain;
  background: rgba(0, 0, 0, 0.04);
}
.msg-img.clickable {
  cursor: zoom-in;
}
.img-preview-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  max-height: 70vh;
  overflow: auto;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 8px;
}
.img-preview-full {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}
.file-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 140px;
}
.media-file {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.img-placeholder {
  width: 120px;
  height: 90px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.06);
  color: #999;
  font-size: 12px;
}
.dl {
  font-size: 12px;
  color: #2080f0;
}
</style>
