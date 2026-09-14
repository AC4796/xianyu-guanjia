/** 闲鱼管家 API 共享类型 */

export interface ApiResponse<T = unknown> {
  success: boolean
  message?: string
  data?: T
  msg?: string
  detail?: string
}

export interface User {
  user_id: number
  username: string
  is_admin: boolean
  email?: string
}

export interface LoginRequest {
  username?: string
  password?: string
  email?: string
  verification_code?: string
  session_id?: string
  captcha_code?: string
}

export interface LoginResponse {
  success: boolean
  message?: string
  token?: string
  user_id?: number
  username?: string
  is_admin?: boolean
}

export interface Account {
  id: string
  cookie: string
  enabled: boolean
  use_ai_reply: boolean
  use_default_reply: boolean
  auto_confirm: boolean
  note?: string
  remark?: string
  pause_duration?: number
  created_at?: string
  updated_at?: string
}

export interface AccountDetail extends Account {
  keywords?: Keyword[]
  keywordCount?: number
  username?: string
  login_password?: string
  show_browser?: boolean
  value?: string
  nickname?: string
  avatar_url?: string
  ai_enabled?: boolean
  chat_running?: boolean
  online?: boolean
  unb?: string
  tracknick?: string
  health_status?: 'normal' | 'abnormal' | string
  health_reason?: string
  last_risk_at?: string
}

export interface Keyword {
  id?: string
  cookie_id?: string
  keyword: string
  reply: string
  item_id?: string
  type?: 'text' | 'image' | 'item' | 'normal'
  image_url?: string
  fuzzy_match?: boolean
  created_at?: string
  updated_at?: string
}

export interface Item {
  id: string | number
  cookie_id: string
  item_id: string
  title?: string
  item_title?: string
  desc?: string
  item_description?: string
  item_detail?: string
  item_detail_parsed?: Record<string, unknown>
  item_category?: string
  price?: string
  item_price?: string
  item_pic?: string
  account_nickname?: string
  account_avatar?: string
  seller_name?: string
  local_status?: 'on' | 'off' | string
  has_sku?: boolean
  is_multi_spec?: number | boolean
  multi_delivery?: boolean
  multi_quantity_delivery?: number | boolean
  want_num?: number | null
  view_count?: number | null
  original_price?: string
  created_at?: string
  updated_at?: string
}

export interface ItemReply {
  id: string
  cookie_id: string
  item_id: string
  title?: string
  content?: string
  reply: string
  created_at?: string
  updated_at?: string
}

export type OrderStatus =
  | 'processing'
  | 'pending_ship'
  | 'processed'
  | 'shipped'
  | 'completed'
  | 'refunding'
  | 'cancelled'
  | 'unknown'
  | string

export interface Order {
  id?: string
  order_id: string
  cookie_id: string
  item_id: string
  buyer_id?: string
  chat_id?: string
  sku_info?: string
  spec_name?: string
  spec_value?: string
  quantity?: number | string
  amount?: string
  status?: OrderStatus
  order_status?: string
  is_bargain?: boolean
  system_shipped?: boolean
  receiver_name?: string
  receiver_phone?: string
  receiver_address?: string
  receiver_city?: string
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

export interface OrderDetail extends Order {
  spec_name?: string
  spec_value?: string
}

export interface CardData {
  id?: number
  name: string
  type: 'api' | 'text' | 'data' | 'image'
  description?: string
  enabled?: boolean
  delay_seconds?: number
  is_multi_spec?: boolean
  spec_name?: string
  spec_value?: string
  api_config?: {
    url: string
    method: string
    timeout?: number
    headers?: string
    params?: string
  }
  text_content?: string
  data_content?: string
  image_url?: string
  created_at?: string
  updated_at?: string
  user_id?: number
}

export interface DeliveryRule {
  id: number
  keyword: string
  card_id: number
  delivery_count: number
  enabled: boolean
  description?: string
  delivery_times?: number
  card_name?: string
  card_type?: string
  is_multi_spec?: boolean
  spec_name?: string
  spec_value?: string
  created_at?: string
  updated_at?: string
}

export interface NotificationChannel {
  id: string
  cookie_id?: string
  name: string
  type: 'qq' | 'dingtalk' | 'feishu' | 'bark' | 'email' | 'webhook' | 'wechat' | 'telegram' | string
  channel_type?: string
  channel_name?: string
  channel_config?: string
  config?: Record<string, unknown>
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface MessageNotification {
  cookie_id: string
  channel_id: number
  channel_name?: string
  enabled: boolean
}

export interface SystemSettings {
  ai_model?: string
  ai_api_key?: string
  ai_api_url?: string
  ai_base_url?: string
  default_reply?: string
  registration_enabled?: boolean
  show_default_login_info?: boolean
  login_captcha_enabled?: boolean
  smtp_server?: string
  smtp_port?: number
  smtp_user?: string
  smtp_password?: string
  smtp_from?: string
  smtp_use_tls?: boolean
  smtp_use_ssl?: boolean
  qq_reply_secret_key?: string
  item_sync_enabled?: boolean
  item_sync_interval?: number
  item_sync_max_pages?: number
  [key: string]: unknown
}

export interface AIReplySettings {
  ai_enabled: boolean
  model_name?: string
  api_key?: string
  base_url?: string
  max_discount_percent?: number
  max_discount_amount?: number
  max_bargain_rounds?: number
  custom_prompts?: string
  enabled?: boolean
}

export interface DefaultReply {
  cookie_id?: string
  enabled: boolean
  reply_content: string
  reply_once?: boolean
  reply_image_url?: string
}

export interface PaginatedOrders {
  success: boolean
  data: Order[]
  total?: number
  page?: number
  page_size?: number
  total_pages?: number
}

export type ShipMode = 'status_only' | 'full_delivery' | 'auto_match' | 'custom'

export interface ManualShipResponse {
  success: boolean
  message?: string
  total: number
  success_count: number
  failed_count: number
  results: Array<{
    order_id: string
    success: boolean
    message: string
  }>
}
