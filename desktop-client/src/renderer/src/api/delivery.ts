import { request } from './http'

export interface CardRow {
  id?: number | string
  name?: string
  type?: string
  data?: string
  content?: string
  enabled?: boolean
  [key: string]: unknown
}

export async function getCards(): Promise<CardRow[]> {
  const res = await request<{ cards?: CardRow[] } | CardRow[]>('/cards')
  return Array.isArray(res) ? res : res.cards || []
}

export const createCard = (data: Partial<CardRow>) =>
  request('/cards', { method: 'POST', json: data })

export const updateCard = (id: string | number, data: Partial<CardRow>) =>
  request(`/cards/${id}`, { method: 'PUT', json: data })

export const deleteCard = (id: string | number) =>
  request(`/cards/${id}`, { method: 'DELETE' })

export interface DeliveryRule {
  id?: number | string
  keyword?: string
  card_id?: number | string
  cookie_id?: string
  enabled?: boolean
  [key: string]: unknown
}

export async function getDeliveryRules(cookieId?: string): Promise<DeliveryRule[]> {
  const q = cookieId ? `?cookie_id=${encodeURIComponent(cookieId)}` : ''
  const res = await request<{ data?: DeliveryRule[]; rules?: DeliveryRule[] } | DeliveryRule[]>(
    `/delivery-rules${q}`
  )
  return Array.isArray(res) ? res : res.data || res.rules || []
}

export const addDeliveryRule = (data: Partial<DeliveryRule>) =>
  request('/delivery-rules', { method: 'POST', json: data })

export const deleteDeliveryRule = (id: string | number) =>
  request(`/delivery-rules/${id}`, { method: 'DELETE' })
