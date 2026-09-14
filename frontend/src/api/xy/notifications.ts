import request from '@/utils/http'
import type { ApiResponse, NotificationChannel, MessageNotification } from './types'

export const getNotificationChannels = async (): Promise<{
  success: boolean
  data?: NotificationChannel[]
}> => {
  const result = await request.get<any[]>({ url: '/notification-channels' })
  const channels = (result || []).map((item: any) => {
    let parsedConfig
    try {
      parsedConfig = typeof item.config === 'string' ? JSON.parse(item.config) : item.config
    } catch {
      parsedConfig = undefined
    }
    return {
      id: String(item.id),
      name: item.name,
      type: item.type,
      config: parsedConfig,
      enabled: item.enabled,
      created_at: item.created_at,
      updated_at: item.updated_at
    }
  })
  return { success: true, data: channels }
}

export const createNotificationChannel = (data: {
  name: string
  type: string
  config: Record<string, unknown>
}) =>
  request.post<ApiResponse>({
    url: '/notification-channels',
    data: { ...data, config: JSON.stringify(data.config) }
  })

export const updateNotificationChannel = (
  channelId: string,
  data: { name?: string; config?: Record<string, unknown>; enabled?: boolean }
) => {
  const payload: Record<string, unknown> = { ...data }
  if ('config' in data) payload.config = JSON.stringify(data.config)
  return request.put<ApiResponse>({ url: `/notification-channels/${channelId}`, data: payload })
}

export const deleteNotificationChannel = (channelId: string) =>
  request.del<ApiResponse>({ url: `/notification-channels/${channelId}` })

export const testNotificationChannel = (channelId: string) =>
  request.post({ url: `/notification-channels/${channelId}/test` })

export const getMessageNotifications = async (): Promise<{
  success: boolean
  data?: MessageNotification[]
}> => {
  const result = await request.get<Record<string, any[]>>({ url: '/message-notifications' })
  const notifications: MessageNotification[] = []
  for (const [cookieId, channelList] of Object.entries(result || {})) {
    if (Array.isArray(channelList)) {
      for (const item of channelList) {
        notifications.push({
          cookie_id: cookieId,
          channel_id: item.channel_id,
          channel_name: item.channel_name,
          enabled: item.enabled
        })
      }
    }
  }
  return { success: true, data: notifications }
}

export const setMessageNotification = (cookieId: string, channelId: number, enabled: boolean) =>
  request.post<ApiResponse>({
    url: `/message-notifications/${cookieId}`,
    data: { channel_id: channelId, enabled }
  })

export const deleteMessageNotification = (notificationId: string) =>
  request.del<ApiResponse>({ url: `/message-notifications/${notificationId}` })

export const deleteAccountNotifications = (cookieId: string) =>
  request.del<ApiResponse>({ url: `/message-notifications/account/${cookieId}` })
