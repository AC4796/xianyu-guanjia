import { request } from './http'

export interface KeywordRow {
  keyword: string
  reply: string
  item_id?: string
  type?: string
  image_url?: string
}

export async function getKeywords(cookieId: string): Promise<KeywordRow[]> {
  const res = await request<KeywordRow[] | { data?: KeywordRow[] }>(
    `/keywords-with-item-id/${encodeURIComponent(cookieId)}`
  )
  return Array.isArray(res) ? res : res?.data || []
}

export const saveKeywords = (cookieId: string, keywords: KeywordRow[]) => {
  const textKeywords = keywords
    .filter((k) => k.type !== 'image')
    .map((k) => ({
      keyword: k.keyword,
      reply: k.reply || '',
      item_id: k.item_id || ''
    }))
  return request<{ success?: boolean; message?: string; msg?: string }>(
    `/keywords-with-item-id/${encodeURIComponent(cookieId)}`,
    { method: 'POST', json: { keywords: textKeywords } }
  )
}

export async function addKeyword(
  cookieId: string,
  data: Partial<KeywordRow>
): Promise<{ success: boolean; message?: string }> {
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
  await saveKeywords(cookieId, keywords)
  return { success: true }
}

export async function updateKeyword(
  cookieId: string,
  oldKeyword: string,
  oldItemId: string,
  data: Partial<KeywordRow>
): Promise<{ success: boolean; message?: string }> {
  const keywords = await getKeywords(cookieId)
  const index = keywords.findIndex(
    (k) => k.keyword === oldKeyword && (k.item_id || '') === (oldItemId || '')
  )
  if (index === -1) return { success: false, message: '关键词不存在' }
  keywords[index] = { ...keywords[index], ...data }
  await saveKeywords(cookieId, keywords)
  return { success: true }
}

export async function deleteKeyword(
  cookieId: string,
  keyword: string,
  itemId: string
): Promise<{ success: boolean }> {
  const keywords = await getKeywords(cookieId)
  const next = keywords.filter(
    (k) => !(k.keyword === keyword && (k.item_id || '') === (itemId || ''))
  )
  await saveKeywords(cookieId, next)
  return { success: true }
}
