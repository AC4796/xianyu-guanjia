import { request } from './http'

export interface LoginResponse {
  success: boolean
  message: string
  user_id?: number | null
  username?: string | null
  is_admin?: boolean | null
}

export interface VerifyResponse {
  authenticated: boolean
  initialized?: boolean
  user_id?: number
  username?: string
  is_admin?: boolean
}

function truthy(v: unknown): boolean {
  return v === true || v === 'true' || v === 1 || v === '1'
}

export const login = (data: { username: string; password: string }) =>
  request<LoginResponse>('/login', { method: 'POST', json: data })

export const verifySession = () => request<VerifyResponse>('/verify')

export const logout = () => request<{ message?: string }>('/logout', { method: 'POST', json: {} })

export async function getLoginCaptchaEnabled(): Promise<boolean> {
  try {
    const settings = await request<Record<string, unknown>>('/system-settings/public')
    return truthy(settings.login_captcha_enabled)
  } catch {
    return false
  }
}

export const generateCaptcha = (sessionId: string) =>
  request<{ success: boolean; captcha_image?: string; message?: string }>('/generate-captcha', {
    method: 'POST',
    json: { session_id: sessionId }
  })

export const verifyCaptcha = (sessionId: string, captchaCode: string) =>
  request<{ success: boolean; message?: string }>('/verify-captcha', {
    method: 'POST',
    json: { session_id: sessionId, captcha_code: captchaCode }
  })
