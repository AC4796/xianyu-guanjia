import request from '@/utils/http'
import type { CardData, ApiResponse } from './types'

export const getCards = async (): Promise<CardData[]> => {
  const res = await request.get<{ cards?: CardData[] } | CardData[]>({ url: '/cards' })
  return Array.isArray(res) ? res : res.cards || []
}

export const getCard = (cardId: string | number) =>
  request.get<CardData>({ url: `/cards/${cardId}` })

export const createCard = (data: Partial<CardData>) =>
  request.post<{ id: number; message: string }>({ url: '/cards', data })

export const updateCard = (cardId: string | number, data: Partial<CardData>) =>
  request.put<ApiResponse>({ url: `/cards/${cardId}`, data })

export const deleteCard = (cardId: string | number) =>
  request.del<ApiResponse>({ url: `/cards/${cardId}` })

export const getCardDetails = (cardId: string | number) =>
  request.get({ url: `/cards/${cardId}/details` })

export const batchDeleteCards = (ids: Array<string | number>) =>
  request.post({ url: '/cards/batch-delete', data: { ids } })

export const importCards = async (file: FormData) => {
  const response = await fetch('/cards/import', {
    method: 'POST',
    credentials: 'include',
    body: file
  })
  return response.json()
}
