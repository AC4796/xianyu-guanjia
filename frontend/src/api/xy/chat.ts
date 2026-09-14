import request from '@/utils/http'

export interface ChatMessage {
  id?: number
  type?: string
  cookie_id: string
  chat_id: string
  buyer_id?: string
  buyer_nick?: string
  buyer_avatar?: string
  content: string
  content_pic?: string
  item_id?: string
  item_title?: string
  item_price?: string
  item_pic?: string
  direction: 'in' | 'out' | string
  ts: number
  account_nickname?: string
}

export const getChatSessions = async (cookieId?: string): Promise<ChatMessage[]> => {
  const res = await request.get<{ success: boolean; data: ChatMessage[] }>({
    url: '/chat/sessions',
    params: cookieId ? { cookie_id: cookieId } : undefined
  })
  return res?.data || []
}

export const getChatMessages = async (
  cookieId: string,
  chatId: string,
  limit = 80,
  sync = false
): Promise<ChatMessage[]> => {
  const res = await request.get<{ success: boolean; data: ChatMessage[] }>({
    url: '/chat/messages',
    params: { cookie_id: cookieId, chat_id: chatId, limit, sync: sync ? 1 : 0 }
  })
  return res?.data || []
}

export const syncChatSessions = (cookieId?: string) =>
  request.post<{ success: boolean; saved?: number; details?: unknown[] }>({
    url: '/chat/sync',
    params: cookieId ? { cookie_id: cookieId } : undefined
  })

export const syncChatMessages = (cookieId: string, chatId: string, limit = 40) =>
  request.post<{ success: boolean; saved?: number; data?: ChatMessage[] }>({
    url: '/chat/sync-messages',
    params: { cookie_id: cookieId, chat_id: chatId, limit }
  })

export const sendChatMessage = (data: {
  cookie_id: string
  chat_id: string
  to_user_id: string
  message: string
}) => request.post<{ success: boolean; message?: string; data?: ChatMessage }>({ url: '/chat/send', data })

export function buildChatWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/chat`
}
