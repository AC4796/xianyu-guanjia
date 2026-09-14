import { request } from './http'

export interface NotificationChannel {
  id: string
  name: string
  type: string
  config?: Record<string, unknown>
  enabled?: boolean
}

export async function getNotificationChannels(): Promise<NotificationChannel[]> {
  const result = await request<any[]>('/notification-channels')
  return (result || []).map((item) => {
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
      enabled: item.enabled
    }
  })
}

export const createNotificationChannel = (data: {
  name: string
  type: string
  config: Record<string, unknown>
}) =>
  request('/notification-channels', {
    method: 'POST',
    json: { ...data, config: JSON.stringify(data.config) }
  })

export const deleteNotificationChannel = (id: string) =>
  request(`/notification-channels/${id}`, { method: 'DELETE' })

export const testNotificationChannel = (id: string) =>
  request(`/notification-channels/${id}/test`, { method: 'POST', json: {} })

export async function getSystemSettings(): Promise<Record<string, string>> {
  const res = await request<Record<string, string> & { data?: Record<string, string> }>(
    '/system-settings'
  )
  return (res as any).data || res || {}
}

export async function updateSystemSetting(key: string, value: string): Promise<void> {
  await request(`/system-settings/${key}`, { method: 'PUT', json: { value } })
}

export const changePassword = (currentPassword: string, newPassword: string) =>
  request('/change-password', {
    method: 'POST',
    json: { current_password: currentPassword, new_password: newPassword }
  })

export const reloadSystemCache = () =>
  request('/admin/reload-cache', { method: 'POST', json: {} })
