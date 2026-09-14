import { request } from './http'

export interface AccountCard {
  id: string
  nickname: string
  avatar_url: string
  bio: string
  unb?: string
  online?: boolean
  enabled?: boolean
}

export async function getAccountDetails(): Promise<AccountCard[]> {
  const data = await request<
    Array<{
      id: string
      nickname?: string
      avatar_url?: string
      bio?: string
      unb?: string
      online?: boolean
      enabled?: boolean
      remark?: string
    }>
  >('/cookies/details')

  return (data || []).map((item) => ({
    id: item.id,
    nickname: item.nickname || item.remark || item.id,
    avatar_url:
      item.avatar_url ||
      `https://api.dicebear.com/7.x/avataaars/svg?seed=${item.unb || item.id}`,
    bio: item.bio || '',
    unb: item.unb,
    online: item.online,
    enabled: item.enabled
  }))
}

export const refreshAccountProfile = (id: string) =>
  request<{
    success: boolean
    nickname?: string
    avatar_url?: string
    bio?: string
    message?: string
  }>(`/cookies/${id}/refresh-profile`, { method: 'POST', json: {} })

export const reconnectAccount = (id: string) =>
  request<{ success?: boolean; message?: string }>(`/cookies/${id}/reconnect`, {
    method: 'POST',
    json: {}
  })
