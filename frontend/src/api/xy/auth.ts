import request from '@/utils/http'
import type { ApiResponse, LoginRequest, LoginResponse } from './types'

export type { LoginRequest, LoginResponse }

export interface GeetestRegisterResponse {
  success: boolean
  code: number
  message: string
  data?: {
    success: number
    gt: string
    challenge: string
    new_captcha: boolean
  }
}

export interface GeetestValidateResponse {
  success: boolean
  code: number
  message: string
}

export const login = (data: LoginRequest): Promise<LoginResponse> =>
  request.post({ url: '/login', data, showErrorMessage: false })

export const verifySession = () =>
  request.get<{
    authenticated: boolean
    initialized?: boolean
    user_id?: number
    username?: string
    is_admin?: boolean
  }>({ url: '/verify', showErrorMessage: false })

export const logout = (): Promise<ApiResponse> => request.post({ url: '/logout', data: {} })

export const getRegistrationStatus = async (): Promise<{ enabled: boolean }> => {
  try {
    const settings = await request.get<Record<string, unknown>>({ url: '/system-settings/public' })
    const value = settings.registration_enabled
    return { enabled: value === true || value === 'true' || value === 1 || value === '1' }
  } catch {
    return { enabled: true }
  }
}

export const generateCaptcha = (sessionId: string) =>
  request.post<{ success: boolean; captcha_image?: string }>({
    url: '/generate-captcha',
    data: { session_id: sessionId }
  })

export const verifyCaptcha = (sessionId: string, captchaCode: string) =>
  request.post<{ success: boolean }>({
    url: '/verify-captcha',
    data: { session_id: sessionId, captcha_code: captchaCode }
  })

export const sendVerificationCode = (email: string, type: string, sessionId: string) =>
  request.post<ApiResponse>({
    url: '/send-verification-code',
    data: { email, type, session_id: sessionId }
  })

export const register = (data: {
  username: string
  password: string
  email: string
  verification_code: string
  session_id: string
}) => request.post<ApiResponse>({ url: '/register', data })

export const getGeetestRegister = () =>
  request.get<GeetestRegisterResponse>({ url: '/geetest/register' })

export const geetestValidate = (data: { challenge: string; validate: string; seccode: string }) =>
  request.post<GeetestValidateResponse>({ url: '/geetest/validate', data })

export const getLoginCaptchaStatus = async (): Promise<{ enabled: boolean }> => {
  try {
    const settings = await request.get<Record<string, unknown>>({ url: '/system-settings/public' })
    const value = settings.login_captcha_enabled
    if (value === undefined || value === null) return { enabled: true }
    return { enabled: value === true || value === 'true' || value === 1 || value === '1' }
  } catch {
    return { enabled: true }
  }
}
