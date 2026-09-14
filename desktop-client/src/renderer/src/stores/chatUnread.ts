/** 聊天未读：菜单红点 + 账号红点 + 提示音 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export interface ChatUnreadItem {
  title: string
  time: string
  content: string
  avatar?: string
  cookie_id?: string
  chat_id?: string
  ts?: number
}

const SOUND_KEY = 'xy_chat_sound_mode'
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

export async function unlockChatAudio(): Promise<void> {
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

function playIncomingBeep(mode: 'on' | 'beep' | 'mute' = 'on'): void {
  if (mode === 'mute') return
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioCtx) return
    if (!audioCtx) audioCtx = new AudioCtx()
    const ctx = audioCtx
    const kick = () => {
      const now = ctx.currentTime
      ;[0, 0.16].forEach((offset, i) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sine'
        osc.frequency.value = i === 0 ? 880 : 1175
        gain.gain.setValueAtTime(0.0001, now + offset)
        gain.gain.exponentialRampToValueAtTime(0.28, now + offset + 0.02)
        gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.15)
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
          u.rate = 1.05
          window.speechSynthesis.speak(u)
        } catch {
          /* ignore */
        }
      }
    }
    if (ctx.state === 'suspended') {
      void ctx.resume().then(kick)
    } else {
      kick()
    }
  } catch {
    /* ignore */
  }
}

export const useChatUnreadStore = defineStore('chatUnread', () => {
  const count = ref(0)
  const items = ref<ChatUnreadItem[]>([])
  const byCookie = ref<Record<string, number>>({})
  const bySession = ref<Record<string, number>>({})
  /** 会话是否已读（打开过） */
  const readSessions = ref<Record<string, boolean>>({})
  const soundMode = ref<'on' | 'beep' | 'mute'>(loadSoundMode())
  /** 去重：同一条消息只计一次未读 */
  const seenKeys = ref<Record<string, number>>({})

  const hasUnread = computed(() => count.value > 0)

  function sessionKey(cookieId?: string, chatId?: string): string {
    return `${cookieId || ''}::${chatId || ''}`
  }

  function msgDedupeKey(msg: {
    cookie_id?: string
    chat_id?: string
    ts?: number
    content?: string
    content_pic?: string
    direction?: string
  }): string {
    return [
      msg.cookie_id || '',
      msg.chat_id || '',
      String(msg.ts || 0),
      msg.direction || 'in',
      String(msg.content || '').slice(0, 80),
      String(msg.content_pic || '').slice(0, 40)
    ].join('|')
  }

  function setSoundMode(mode: 'on' | 'beep' | 'mute'): void {
    soundMode.value = mode
    localStorage.setItem(SOUND_KEY, mode)
    if (mode !== 'mute') void unlockChatAudio()
  }

  function pushIncoming(msg: {
    content?: string
    content_pic?: string
    buyer_nick?: string
    buyer_id?: string
    buyer_avatar?: string
    cookie_id?: string
    chat_id?: string
    ts?: number
    direction?: string
    source?: string
  }): void {
    if (msg.direction === 'out' || msg.direction === 'sync') return
    if (msg.source === 'session_sync') return
    const content = String(msg.content || '')
    if (content === '[会话]' || content.startsWith('[会话]')) return

    const dk = msgDedupeKey(msg)
    const now = Date.now()
    if (seenKeys.value[dk] && now - seenKeys.value[dk] < 120000) return
    seenKeys.value[dk] = now
    // 控制去重表大小
    const keys = Object.keys(seenKeys.value)
    if (keys.length > 400) {
      const next: Record<string, number> = {}
      keys.slice(-200).forEach((k) => {
        next[k] = seenKeys.value[k]
      })
      seenKeys.value = next
    }

    count.value += 1
    if (msg.cookie_id) {
      byCookie.value[msg.cookie_id] = (byCookie.value[msg.cookie_id] || 0) + 1
    }
    if (msg.cookie_id && msg.chat_id) {
      const sk = sessionKey(msg.cookie_id, msg.chat_id)
      bySession.value[sk] = (bySession.value[sk] || 0) + 1
      readSessions.value[sk] = false
    }
    const nick = msg.buyer_nick || msg.buyer_id || '买家'
    items.value.unshift({
      title: `${nick}: ${content.slice(0, 40)}`,
      time: new Date().toLocaleString('zh-CN'),
      content,
      avatar: msg.buyer_avatar,
      cookie_id: msg.cookie_id,
      chat_id: msg.chat_id,
      ts: msg.ts
    })
    if (items.value.length > 50) items.value = items.value.slice(0, 50)
    playIncomingBeep(soundMode.value)
  }

  function clearSession(cookieId?: string, chatId?: string): void {
    if (!cookieId || !chatId) return
    const sk = sessionKey(cookieId, chatId)
    const n = bySession.value[sk] || 0
    if (n > 0) {
      bySession.value[sk] = 0
      count.value = Math.max(0, count.value - n)
      byCookie.value[cookieId] = Math.max(0, (byCookie.value[cookieId] || 0) - n)
    }
    readSessions.value[sk] = true
    items.value = items.value.filter((it) => !(it.cookie_id === cookieId && it.chat_id === chatId))
  }

  function cookieUnread(cookieId: string): number {
    return byCookie.value[cookieId] || 0
  }

  function sessionUnread(cookieId: string, chatId: string): number {
    return bySession.value[sessionKey(cookieId, chatId)] || 0
  }

  function clearAll(): void {
    count.value = 0
    byCookie.value = {}
    bySession.value = {}
    items.value = []
    const next: Record<string, boolean> = {}
    for (const sk of Object.keys(readSessions.value)) {
      next[sk] = true
    }
    readSessions.value = next
  }

  return {
    count,
    items,
    byCookie,
    bySession,
    readSessions,
    soundMode,
    hasUnread,
    setSoundMode,
    pushIncoming,
    clearSession,
    clearAll,
    cookieUnread,
    sessionUnread,
    sessionKey
  }
})
