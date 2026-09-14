import request from '@/utils/http'
import type { Item, ItemReply, ApiResponse } from './types'

export const getItems = async (cookieId?: string): Promise<Item[]> => {
  const res = await request.get<{ items?: Item[] } | Item[]>({
    url: '/items',
    params: cookieId ? { cookie_id: cookieId } : undefined
  })
  return Array.isArray(res) ? res : res.items || []
}

export const syncItemsFromAccount = (cookieId: string) =>
  request.post({ url: '/items/get-all-from-account', data: { cookie_id: cookieId } })

export const deleteItem = (cookieId: string, itemId: string) =>
  request.del({ url: `/items/${cookieId}/${itemId}` })

export const batchDeleteItems = (items: Array<{ cookie_id: string; item_id: string }>) =>
  request.post({ url: '/items/batch-delete', data: { items } })

export const createItem = (cookieId: string, data: Partial<Item>) =>
  request.post({ url: `/items/${cookieId}`, data })

export const updateItem = (cookieId: string, itemId: string, data: Partial<Item>) =>
  request.put({ url: `/items/${cookieId}/${itemId}`, data })

export const updateItemLocalStatus = (
  cookieId: string,
  itemId: string,
  localStatus: 'on' | 'off'
) =>
  request.put({
    url: `/items/${cookieId}/${itemId}/local-status`,
    data: { local_status: localStatus }
  })

export const polishItem = (cookieId: string, itemId: string) =>
  request.post({ url: `/items/${cookieId}/${itemId}/polish` })

export const updateItemMultiQuantityDelivery = (
  cookieId: string,
  itemId: string,
  enabled: boolean
) =>
  request.put({
    url: `/items/${cookieId}/${itemId}/multi-quantity-delivery`,
    data: { multi_quantity_delivery: enabled }
  })

export const updateItemMultiSpec = (cookieId: string, itemId: string, enabled: boolean) =>
  request.put({
    url: `/items/${cookieId}/${itemId}/multi-spec`,
    data: { is_multi_spec: enabled }
  })

export const getItemReplies = async (cookieId?: string): Promise<ItemReply[]> => {
  const url = cookieId ? `/item-replies/${cookieId}` : '/item-replies'
  const res = await request.get<{ data?: ItemReply[]; items?: ItemReply[] } | ItemReply[]>({
    url
  })
  const list = Array.isArray(res) ? res : res.data || res.items || []
  return list.map((r) => ({
    ...r,
    id: r.id || `${r.cookie_id}::${r.item_id}`,
    reply: r.reply || (r as any).reply_content || '',
    title: r.title || (r as any).item_title || ''
  }))
}

export const addItemReply = (data: Partial<ItemReply>) =>
  request.post<ApiResponse>({
    url: '/item-replies',
    data: {
      cookie_id: data.cookie_id,
      item_id: data.item_id,
      reply: data.reply,
      reply_content: data.reply,
      title: data.title
    }
  })

export const updateItemReply = (id: string, data: Partial<ItemReply>) =>
  request.put<ApiResponse>({
    url: `/item-replies/${id}`,
    data: {
      cookie_id: data.cookie_id,
      item_id: data.item_id,
      reply: data.reply,
      reply_content: data.reply,
      title: data.title
    }
  })

export const deleteItemReply = (id: string) =>
  request.del<ApiResponse>({ url: `/item-replies/${id}` })

export const batchDeleteItemReplies = (ids: string[]) =>
  request.post({ url: '/item-replies/batch-delete', data: { ids } })
