import request from '@/utils/http'
import type { ApiResponse, SystemSettings, AIReplySettings } from './types'

export const getSystemSettings = async (): Promise<SystemSettings> => {
  const res = await request.get<{ data?: SystemSettings } & SystemSettings>({
    url: '/system-settings'
  })
  return (res as any).data || res
}

export const updateSystemSettings = async (settings: Partial<SystemSettings>) => {
  const promises = Object.entries(settings).map(([key, value]) =>
    request.put({ url: `/system-settings/${key}`, data: { value: String(value) } })
  )
  await Promise.all(promises)
  return { success: true, message: 'Settings saved' } as ApiResponse
}

export const changePassword = (currentPassword: string, newPassword: string) =>
  request.post<ApiResponse>({
    url: '/change-password',
    data: { current_password: currentPassword, new_password: newPassword }
  })

export const getAISettings = (cookieId: string) =>
  request.get<AIReplySettings>({ url: `/ai-reply-settings/${cookieId}` })

export const updateAISettings = (cookieId: string, settings: Partial<AIReplySettings>) =>
  request.put({ url: `/ai-reply-settings/${cookieId}`, data: settings })

export const testAIConnection = (cookieId: string) =>
  request.post({
    url: `/ai-reply-test/${cookieId}`,
    data: { message: '你好，这是一条测试消息' }
  })

export const getBackupList = () => request.get({ url: '/backup/list' })

export const downloadDatabaseBackup = async () => {
  const response = await fetch('/backup/download', { credentials: 'include' })
  return response.blob()
}

export const uploadDatabaseBackup = async (file: FormData) => {
  const response = await fetch('/backup/upload', {
    method: 'POST',
    credentials: 'include',
    body: file
  })
  return response.json()
}

export const reloadSystemCache = () => request.post({ url: '/admin/reload-cache' })
