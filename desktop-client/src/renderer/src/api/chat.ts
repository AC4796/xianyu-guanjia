import { request, apiBase } from './http'

export interface ChatMessage {
  id?: number
  cookie_id: string
  chat_id: string
  buyer_id?: string
  buyer_nick?: string
  buyer_avatar?: string
  content: string
  content_pic?: string
  direction: string
  ts: number
  item_title?: string
  item_pic?: string
  [key: string]: unknown
}

export async function getChatSessions(cookieId?: string): Promise<ChatMessage[]> {
  const q = cookieId ? `?cookie_id=${encodeURIComponent(cookieId)}` : ''
  const res = await request<{ success?: boolean; data?: ChatMessage[] }>(`/chat/sessions${q}`)
  return res?.data || []
}

export async function getChatMessages(
  cookieId: string,
  chatId: string,
  limit = 80
): Promise<ChatMessage[]> {
  const q = new URLSearchParams({
    cookie_id: cookieId,
    chat_id: chatId,
    limit: String(limit)
  })
  const res = await request<{ success?: boolean; data?: ChatMessage[] }>(
    `/chat/messages?${q.toString()}`
  )
  return res?.data || []
}

export const syncChatSessions = (cookieId?: string) => {
  const q = cookieId ? `?cookie_id=${encodeURIComponent(cookieId)}` : ''
  return request(`/chat/sync${q}`, { method: 'POST', json: {} })
}

export const sendChatMessage = (data: {
  cookie_id: string
  chat_id: string
  to_user_id: string
  message: string
  content_pic?: string
}) =>
  request<{ success?: boolean; message?: string; data?: ChatMessage }>('/chat/send', {
    method: 'POST',
    json: data
  })

/** 采集「沟通」：创建/复用与对方的会话 */
export const ensureChatSession = (data: {
  cookie_id: string
  to_user_id: string
  item_id?: string
  buyer_nick?: string
  buyer_avatar?: string
  item_title?: string
  item_pic?: string
}) =>
  request<{
    success?: boolean
    data?: {
      chat_id: string
      buyer_id?: string
      buyer_nick?: string
      item_id?: string
      reused?: boolean
    }
  }>('/chat/ensure', { method: 'POST', json: data })

export function buildChatWsUrl(): string {
  const base = apiBase()
  if (base) {
    return base.replace(/^http/, 'ws') + '/ws/chat'
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/chat`
}
