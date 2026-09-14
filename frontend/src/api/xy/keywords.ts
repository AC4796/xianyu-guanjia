import request from '@/utils/http'
import type { Keyword, ApiResponse, DefaultReply } from './types'

export const getKeywords = (cookieId: string): Promise<Keyword[]> =>
  request.get({ url: `/keywords-with-item-id/${cookieId}` })

export const saveKeywords = (cookieId: string, keywords: Keyword[]) => {
  const textKeywords = keywords
    .filter((k) => k.type !== 'image')
    .map((k) => ({
      keyword: k.keyword,
      reply: k.reply || '',
      item_id: k.item_id || ''
    }))
  return request.post<ApiResponse>({
    url: `/keywords-with-item-id/${cookieId}`,
    data: { keywords: textKeywords }
  })
}

export const addKeyword = async (cookieId: string, data: Partial<Keyword>) => {
  const keywords = await getKeywords(cookieId)
  const exists = keywords.some(
    (k) => k.keyword === data.keyword && (k.item_id || '') === (data.item_id || '')
  )
  if (exists) return { success: false, message: '该关键词已存在' }
  keywords.push({
    keyword: data.keyword || '',
    reply: data.reply || '',
    item_id: data.item_id || '',
    type: 'text'
  })
  return saveKeywords(cookieId, keywords)
}

export const updateKeyword = async (
  cookieId: string,
  oldKeyword: string,
  oldItemId: string,
  data: Partial<Keyword>
) => {
  const keywords = await getKeywords(cookieId)
  const index = keywords.findIndex(
    (k) => k.keyword === oldKeyword && (k.item_id || '') === (oldItemId || '')
  )
  if (index === -1) return { success: false, message: '关键词不存在' }
  keywords[index] = { ...keywords[index], ...data }
  return saveKeywords(cookieId, keywords)
}

export const deleteKeyword = async (cookieId: string, keyword: string, itemId: string) => {
  const keywords = await getKeywords(cookieId)
  const next = keywords.filter(
    (k) => !(k.keyword === keyword && (k.item_id || '') === (itemId || ''))
  )
  return saveKeywords(cookieId, next)
}

export const getDefaultReply = async (cookieId: string): Promise<DefaultReply> => {
  const result = await request.get<any>({ url: `/api/default-reply/${cookieId}` })
  return {
    cookie_id: cookieId,
    enabled: result.enabled || false,
    reply_content: result.reply_content || '',
    reply_once: result.reply_once || false,
    reply_image_url: result.reply_image_url || ''
  }
}

export const updateDefaultReply = (cookieId: string, data: Partial<DefaultReply>) =>
  request.put<ApiResponse>({
    url: `/api/default-reply/${cookieId}`,
    data: {
      enabled: data.enabled ?? false,
      reply_content: data.reply_content || '',
      reply_once: data.reply_once ?? false,
      reply_image_url: data.reply_image_url || ''
    }
  })
