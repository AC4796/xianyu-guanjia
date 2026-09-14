import request from '@/utils/http'
import type { DeliveryRule, ApiResponse } from './types'

export const getDeliveryRules = async (): Promise<DeliveryRule[]> => {
  const res = await request.get<{ data?: DeliveryRule[]; rules?: DeliveryRule[] } | DeliveryRule[]>(
    { url: '/delivery-rules' }
  )
  return Array.isArray(res) ? res : res.data || res.rules || []
}

export const addDeliveryRule = (data: Partial<DeliveryRule>) =>
  request.post<ApiResponse>({ url: '/delivery-rules', data })

export const updateDeliveryRule = (id: number | string, data: Partial<DeliveryRule>) =>
  request.put<ApiResponse>({ url: `/delivery-rules/${id}`, data })

export const deleteDeliveryRule = (id: number | string) =>
  request.del<ApiResponse>({ url: `/delivery-rules/${id}` })

export const getDeliveryRulesByAccount = (cookieId: string) =>
  request.get<DeliveryRule[]>({ url: `/delivery-rules`, params: { cookie_id: cookieId } })
