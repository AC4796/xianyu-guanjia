import { request } from './http'

export interface SensitiveHit {
  word?: string
  start?: number
  end?: number
  category?: string
  level?: string
  snippet?: string
}

export interface SensitiveDetectResult {
  platform?: string
  ok?: boolean
  level?: string
  hit_count?: number
  hits?: SensitiveHit[]
  categories?: string[]
  word_count?: number
  extra_loaded?: number
}

export interface SensitiveRewriteResult {
  platform?: string
  mode?: string
  deep?: boolean
  rounds?: number
  original?: string
  rewritten?: string
  changed?: boolean
  clean?: boolean
  remaining_hits?: number
  replacements?: Array<{ from?: string; to?: string; word?: string; category?: string }>
  detect?: SensitiveDetectResult
  final_detect?: SensitiveDetectResult
  word_count?: number
  extra_loaded?: number
}

export interface SensitivePlatform {
  id: string
  name: string
  ready: boolean
}

export const listSensitivePlatforms = () =>
  request<{ success?: boolean; data?: SensitivePlatform[] }>('/sensitive/platforms')

export const detectSensitive = (body: {
  platform?: string
  text: string
  title?: string
  desc?: string
}) =>
  request<{ success?: boolean; data?: SensitiveDetectResult & { title?: any; desc?: any } }>(
    '/sensitive/detect',
    { method: 'POST', json: body }
  )

export const rewriteSensitive = (body: {
  platform?: string
  text: string
  mode?: 'mask' | 'replace' | 'smart'
  deep?: boolean
}) =>
  request<{ success?: boolean; data?: SensitiveRewriteResult }>('/sensitive/rewrite', {
    method: 'POST',
    json: body
  })

export const reloadSensitiveLexicon = (platform = 'goofish') =>
  request<{ success?: boolean; data?: { word_count?: number; extra_loaded?: number } }>(
    '/sensitive/reload',
    { method: 'POST', json: { platform } }
  )
