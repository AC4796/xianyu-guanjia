/** 在线聊天未读：菜单红点 + 顶部通知 + 系统播报 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useMenuStore } from './menu'

export interface ChatUnreadItem {
  title: string
  time: string
  content: string
  avatar?: string
  cookie_id?: string
  chat_id?: string
  ts?: number
}

const SOUND_KEY = 'xy_chat_sound_mode' // on | beep | mute
let audioCtx: AudioContext | null = null
let audioUnlocked = false

function loadSoundMode(): 'on' | 'beep' | 'mute' {
  try {
    const v = localStorage.getItem(SOUND_KEY)
    if (v === 'mute' || v === 'beep' || v === 'on') return v
  } catch {
    /* ignore */
  }
  return 'on'
}

export async function unlockChatAudio() {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioCtx) return
    if (!audioCtx) audioCtx = new AudioCtx()
    if (audioCtx.state === 'suspended') await audioCtx.resume()
    audioUnlocked = true
  } catch {
    /* ignore */
  }
}

function playIncomingBeep(mode: 'on' | 'beep' | 'mute' = 'on') {
  if (mode === 'mute') return
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioCtx) return
    if (!audioCtx) audioCtx = new AudioCtx()
    const ctx = audioCtx
    if (ctx.state === 'suspended') {
      // 需用户手势解锁；静默失败
      void ctx.resume().then(() => {
        audioUnlocked = true
      })
    }
    const now = ctx.currentTime
    ;[0, 0.18].forEach((offset, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = i === 0 ? 880 : 1175
      gain.gain.setValueAtTime(0.0001, now + offset)
      gain.gain.exponentialRampToValueAtTime(0.22, now + offset + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.16)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(now + offset)
      osc.stop(now + offset + 0.18)
    })
    if (mode === 'on' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel()
        const u = new SpeechSynthesisUtterance('来消息了')
        u.lang = 'zh-CN'
        u.rate = 1.1
        u.volume = 1
        window.speechSynthesis.speak(u)
      } catch {
        /* ignore */
      }
    }
  } catch {
    /* ignore */
  }
}

export const useChatUnreadStore = defineStore('chatUnreadStore', () => {
  const count = ref(0)
  const items = ref<ChatUnreadItem[]>([])
  /** 按账号累计未读 */
  const byCookie = ref<Record<string, number>>({})
  /** 按会话累计未读 key=cookie_id::chat_id */
  const bySession = ref<Record<string, number>>({})
  const soundMode = ref<'on' | 'beep' | 'mute'>(loadSoundMode())

  const hasUnread = computed(() => count.value > 0)
  const audioReady = computed(() => audioUnlocked)

  function setSoundMode(mode: 'on' | 'beep' | 'mute') {
    soundMode.value = mode
    try {
      localStorage.setItem(SOUND_KEY, mode)
    } catch {
      /* ignore */
    }
    if (mode !== 'mute') void unlockChatAudio()
  }

  function sessionKey(cookieId?: string, chatId?: string) {
    return `${cookieId || ''}::${chatId || ''}`
  }

  function _syncMenuBadge() {
    const menuStore = useMenuStore()
    const walk = (list: any[]) => {
      for (const m of list || []) {
        const title = m?.meta?.title || ''
        const path = String(m?.path || '')
        const name = String(m?.name || '')
        const hitChild =
          title === '在线聊天' || path.includes('online-chat') || name === 'OnlineChat'
        const hitParent = title === '消息通知' || path === '/notify' || name === 'Notify'
        if (hitChild || hitParent) {
          if (!m.meta) m.meta = {}
          m.meta.showBadge = count.value > 0
        }
        if (m.children?.length) walk(m.children)
      }
    }
    walk(menuStore.menuList as any[])
  }

  function pushIncoming(msg: {
    content?: string
    buyer_nick?: string
    buyer_id?: string
    buyer_avatar?: string
    cookie_id?: string
    chat_id?: string
    ts?: number
    direction?: string
  }) {
    if (msg.direction === 'out') return
    count.value += 1
    if (msg.cookie_id) {
      byCookie.value[msg.cookie_id] = (byCookie.value[msg.cookie_id] || 0) + 1
    }
    if (msg.cookie_id && msg.chat_id) {
      const sk = sessionKey(msg.cookie_id, msg.chat_id)
      bySession.value[sk] = (bySession.value[sk] || 0) + 1
    }
    const nick = msg.buyer_nick || msg.buyer_id || '买家'
    const time = msg.ts
      ? new Date(msg.ts > 1e12 ? msg.ts : msg.ts * 1000).toLocaleString('zh-CN')
      : new Date().toLocaleString('zh-CN')
    items.value.unshift({
      title: `${nick}: ${(msg.content || '').slice(0, 40)}`,
      time,
      content: msg.content || '',
      avatar: msg.buyer_avatar,
      cookie_id: msg.cookie_id,
      chat_id: msg.chat_id,
      ts: msg.ts
    })
    if (items.value.length > 50) items.value = items.value.slice(0, 50)
    _syncMenuBadge()
    playIncomingBeep(soundMode.value)
  }

  function clearSession(cookieId?: string, chatId?: string) {
    if (!cookieId || !chatId) return
    const sk = sessionKey(cookieId, chatId)
    const n = bySession.value[sk] || 0
    if (n > 0) {
      bySession.value[sk] = 0
      count.value = Math.max(0, count.value - n)
      byCookie.value[cookieId] = Math.max(0, (byCookie.value[cookieId] || 0) - n)
    }
    items.value = items.value.filter((it) => !(it.cookie_id === cookieId && it.chat_id === chatId))
    _syncMenuBadge()
  }

  function clearCookie(cookieId?: string) {
    if (!cookieId) return
    const n = byCookie.value[cookieId] || 0
    if (n > 0) {
      byCookie.value[cookieId] = 0
      count.value = Math.max(0, count.value - n)
      Object.keys(bySession.value).forEach((k) => {
        if (k.startsWith(`${cookieId}::`)) bySession.value[k] = 0
      })
    }
    items.value = items.value.filter((it) => it.cookie_id !== cookieId)
    _syncMenuBadge()
  }

  function clear() {
    count.value = 0
    items.value = []
    byCookie.value = {}
    bySession.value = {}
    _syncMenuBadge()
  }

  function clearOne() {
    if (items.value.length) items.value = items.value.slice(1)
    if (count.value > 0) count.value -= 1
    _syncMenuBadge()
  }

  return {
    count,
    items,
    byCookie,
    bySession,
    hasUnread,
    soundMode,
    audioReady,
    setSoundMode,
    unlockChatAudio,
    sessionKey,
    pushIncoming,
    clear,
    clearOne,
    clearSession,
    clearCookie,
    playIncomingBeep: () => playIncomingBeep(soundMode.value)
  }
})
