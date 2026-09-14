import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { buildChatWsUrl } from '../api/chat'
import { useChatUnreadStore } from '../stores/chatUnread'

let sharedWs: WebSocket | null = null
let sharedRefCount = 0
let pingTimer: ReturnType<typeof setInterval> | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
/** 消息页是否挂载：未读只由全局计一次，消息页只负责刷新 UI */
let messagesPageMounted = 0

export function setMessagesPageActive(active: boolean): void {
  messagesPageMounted = Math.max(0, messagesPageMounted + (active ? 1 : -1))
}

function ensureSharedWs(): void {
  if (sharedWs && (sharedWs.readyState === WebSocket.OPEN || sharedWs.readyState === WebSocket.CONNECTING)) {
    return
  }
  const unread = useChatUnreadStore()
  const ws = new WebSocket(buildChatWsUrl())
  sharedWs = ws
  ws.onopen = () => {
    if (pingTimer) clearInterval(pingTimer)
    pingTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)
  }
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(String(ev.data || ''))
      if (data.type === 'pong' || data.type === 'connected') return
      if (data.type !== 'chat_message' && !data.chat_id) return
      window.dispatchEvent(new CustomEvent('xy-chat-message', { detail: data }))
      if (data.direction === 'out' || data.direction === 'sync') return
      if (data.source === 'session_sync') return
      const content = String(data.content || '')
      if (content === '[会话]' || content.startsWith('[会话]')) return
      // 正在看该会话时不计未读（由消息页 clearSession；合并会话可能有多个 chat_id）
      const sk = `${data.cookie_id || ''}::${data.chat_id || ''}`
      const viewing = String((window as any).__xyActiveChatKey || '')
      const viewingKeys = (window as any).__xyActiveChatKeys as string[] | undefined
      if (viewing && viewing === sk) return
      if (Array.isArray(viewingKeys) && viewingKeys.includes(sk)) return
      unread.pushIncoming(data)
    } catch {
      /* ignore */
    }
  }
  ws.onclose = () => {
    sharedWs = null
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (sharedRefCount > 0) {
      reconnectTimer = setTimeout(ensureSharedWs, 3000)
    }
  }
}

/** 工作台挂载后保持全局 WS，非消息页也能红点+提示音 */
export function useGlobalChatWs() {
  const connected = ref(false)
  onMounted(() => {
    sharedRefCount += 1
    ensureSharedWs()
    connected.value = true
  })
  onBeforeUnmount(() => {
    sharedRefCount = Math.max(0, sharedRefCount - 1)
    if (sharedRefCount === 0) {
      if (pingTimer) clearInterval(pingTimer)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      try {
        sharedWs?.close()
      } catch {
        /* ignore */
      }
      sharedWs = null
    }
  })
  return { connected }
}

export function isOnMessagesRoute(route = useRoute()): boolean {
  return String(route.name || '') === 'messages' || String(route.path || '').includes('messages')
}
