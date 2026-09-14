import { request } from './http'

export interface QrGenerateResult {
  success: boolean
  session_id?: string
  qr_code_url?: string
  message?: string
  expire_seconds?: number
  remain_seconds?: number
}

export interface QrCheckResult {
  success?: boolean
  status?: string
  message?: string
  remain_seconds?: number
  expire_seconds?: number
  account_info?: {
    account_id?: string
    nickname?: string
    avatar_url?: string
    bio?: string
    is_new_account?: boolean
  }
}

export const generateQRLogin = () =>
  request<QrGenerateResult>('/qr-login/generate', { method: 'POST', json: {} })

export const checkQRLoginStatus = (sessionId: string) =>
  request<QrCheckResult>(`/qr-login/check/${sessionId}`)
