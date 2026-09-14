import { request } from './http'

export interface ItemReplyRow {
  id?: string
  cookie_id?: string
  item_id?: string
  reply?: string
  reply_content?: string
  title?: string
  item_title?: string
  [key: string]: unknown
}

function normalize(r: ItemReplyRow): ItemReplyRow {
  return {
    ...r,
    id: r.id || `${r.cookie_id || ''}::${r.item_id || ''}`,
    reply: r.reply || r.reply_content || '',
    title: r.title || r.item_title || ''
  }
}

export async function getItemReplies(cookieId?: string): Promise<ItemReplyRow[]> {
  const url = cookieId
    ? `/item-replies/${encodeURIComponent(cookieId)}`
    : '/item-replies'
  const res = await request<{ data?: ItemReplyRow[]; items?: ItemReplyRow[] } | ItemReplyRow[]>(
    url
  )
  const list = Array.isArray(res) ? res : res.data || res.items || []
  return list.map(normalize)
}

export const addItemReply = (data: Partial<ItemReplyRow>) =>
  request<{ success?: boolean; message?: string }>('/item-replies', {
    method: 'POST',
    json: {
      cookie_id: data.cookie_id,
      item_id: data.item_id,
      reply: data.reply,
      reply_content: data.reply,
      title: data.title
    }
  })

export const updateItemReply = (id: string, data: Partial<ItemReplyRow>) =>
  request<{ success?: boolean; message?: string }>(`/item-replies/${encodeURIComponent(id)}`, {
    method: 'PUT',
    json: {
      cookie_id: data.cookie_id,
      item_id: data.item_id,
      reply: data.reply,
      reply_content: data.reply,
      title: data.title
    }
  })

export const deleteItemReply = (id: string) =>
  request<{ success?: boolean; message?: string }>(`/item-replies/${encodeURIComponent(id)}`, {
    method: 'DELETE'
  })
