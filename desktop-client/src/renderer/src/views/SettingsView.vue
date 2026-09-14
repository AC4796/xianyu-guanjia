<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NDivider,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NRadio,
  NRadioGroup,
  NSpace,
  NSwitch,
  NTabPane,
  NTabs,
  NText,
  NTimePicker,
  useMessage
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  getAIReplySettings,
  getAutomationSettings,
  testAIConnection,
  updateAIReplySettings,
  updateAutomationSettings,
  type AIReplySettings,
  type AutomationSettings
} from '../api/automation'
import { changePassword } from '../api/system'

const message = useMessage()
const accountStore = useAccountStore()
const loading = ref(false)
const savingAuto = ref(false)
const savingAi = ref(false)
const testingAi = ref(false)
const activeTab = ref('client')

const autoForm = ref<AutomationSettings | null>(null)
const polishTimeMs = ref<number | null>(null)
const aiForm = ref<AIReplySettings | null>(null)
const pwd = ref({ current: '', next: '', confirm: '' })

const openAtLogin = ref(false)
const openAtLoginLoading = ref(false)
const openAtLoginSaving = ref(false)

function hasDesktopApi(): boolean {
  return typeof window !== 'undefined' && !!(window as any).api
}

function hasOpenAtLoginApi(): boolean {
  return hasDesktopApi() && typeof (window as any).api?.getOpenAtLogin === 'function'
}

async function loadOpenAtLogin(): Promise<void> {
  if (!hasOpenAtLoginApi()) return
  openAtLoginLoading.value = true
  try {
    const s = await window.api.getOpenAtLogin()
    openAtLogin.value = !!s.openAtLogin
  } catch {
    openAtLogin.value = false
  } finally {
    openAtLoginLoading.value = false
  }
}

async function onToggleOpenAtLogin(v: boolean): Promise<void> {
  if (!hasOpenAtLoginApi() || typeof window.api?.setOpenAtLogin !== 'function') {
    message.warning('请完全退出并重新打开桌面客户端后再试（需加载最新主进程）')
    openAtLogin.value = false
    return
  }
  openAtLoginSaving.value = true
  try {
    const res = await window.api.setOpenAtLogin(v)
    openAtLogin.value = !!res.openAtLogin
    if (!res.ok) {
      message.error(res.message || '设置失败')
      return
    }
    message.success(v ? '已开启开机自启动' : '已关闭开机自启动')
  } catch (e: any) {
    openAtLogin.value = !v
    message.error(e?.message || '设置失败')
  } finally {
    openAtLoginSaving.value = false
  }
}

function parseHmToMs(hm: string): number | null {
  const m = String(hm || '').match(/^(\d{1,2}):(\d{2})$/)
  if (!m) return null
  const d = new Date()
  d.setHours(Number(m[1]), Number(m[2]), 0, 0)
  return d.getTime()
}

function msToHm(ms: number | null): string {
  if (ms == null) return '09:00'
  const d = new Date(ms)
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${mi}`
}

async function load(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    autoForm.value = null
    aiForm.value = null
    return
  }
  loading.value = true
  try {
    const [auto, ai] = await Promise.all([getAutomationSettings(cid), getAIReplySettings(cid)])
    autoForm.value = {
      ...auto,
      unpaid_markup_type: (auto as any).unpaid_markup_type || 'amount',
      unpaid_markup_value: Number((auto as any).unpaid_markup_value || 0),
      unpaid_repricing_delay_sec: Number((auto as any).unpaid_repricing_delay_sec ?? 30),
      dropship_pay_password: (auto as any).dropship_pay_password || ''
    }
    polishTimeMs.value = parseHmToMs(auto.daily_polish_time || '09:00')
    aiForm.value = {
      ai_enabled: !!ai.ai_enabled,
      model_name: ai.model_name || 'qwen-plus',
      api_key: ai.api_key || '',
      base_url: ai.base_url || 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      max_discount_percent: Number(ai.max_discount_percent ?? 10),
      max_discount_amount: Number(ai.max_discount_amount ?? 100),
      max_bargain_rounds: Number(ai.max_bargain_rounds ?? 3),
      custom_prompts: ai.custom_prompts || '',
      auto_apply_quote: !!(ai as any).auto_apply_quote
    }
  } catch (e: any) {
    if (e?.status === 401) {
      message.error('登录已过期，请重新登录后再打开系统设置')
    } else if (e?.status === 404) {
      message.error('接口未找到(404)：请确认已重启桌面端（代理需包含 automation-settings）')
    } else {
      message.error(e?.message || '加载设置失败')
    }
  } finally {
    loading.value = false
  }
}

async function saveAuto(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid || !autoForm.value) return
  savingAuto.value = true
  try {
    autoForm.value.daily_polish_time = msToHm(polishTimeMs.value)
    await updateAutomationSettings(cid, autoForm.value)
    message.success('自动化规则已保存（账号在线后按规则执行）')
    await load()
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    savingAuto.value = false
  }
}

async function saveAi(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid || !aiForm.value) return
  if (aiForm.value.ai_enabled && autoForm.value?.unpaid_repricing) {
    message.warning('已开启 AI 议价时，建议关闭「拍下未付款自动改价」，避免冲突')
  }
  savingAi.value = true
  try {
    await updateAIReplySettings(cid, aiForm.value)
    message.success('AI 助手设置已保存')
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    savingAi.value = false
  }
}

async function onTestAi(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) return
  testingAi.value = true
  try {
    const res: any = await testAIConnection(cid)
    const reply = res?.reply || res?.data?.reply || res?.message || JSON.stringify(res)
    message.success(`AI 测试回复：${String(reply).slice(0, 120)}`)
  } catch (e: any) {
    message.error(e?.message || 'AI 测试失败')
  } finally {
    testingAi.value = false
  }
}

async function onChangePwd(): Promise<void> {
  if (!pwd.value.next || pwd.value.next !== pwd.value.confirm) {
    message.warning('两次新密码不一致')
    return
  }
  try {
    await changePassword(pwd.value.current, pwd.value.next)
    message.success('密码已修改')
    pwd.value = { current: '', next: '', confirm: '' }
  } catch (e: any) {
    message.error(e?.message || '修改失败')
  }
}

onMounted(() => {
  void load()
  void loadOpenAtLogin()
})
watch(
  () => accountStore.activeCookieId,
  () => void load()
)
</script>

<template>
  <n-space vertical :size="12">
    <AccountTabs @change="load" />
    <n-text depth="3" style="font-size: 12px">
      设置按标签页分组。「客户端」为软件本身设置；其余规则绑定当前选中账号。
    </n-text>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane name="client" tab="客户端">
        <n-card size="small" style="margin-top: 8px; max-width: 560px">
          <n-form label-placement="left" label-width="140">
            <n-form-item label="开机自动启动">
              <n-space vertical :size="6">
                <n-switch
                  :value="openAtLogin"
                  :loading="openAtLoginLoading || openAtLoginSaving"
                  :disabled="!hasOpenAtLoginApi()"
                  @update:value="onToggleOpenAtLogin"
                />
                <n-text depth="3" style="font-size: 12px">
                  开启后，Windows 登录时会自动打开闲鱼管家（并拉起本地服务）。请使用本机安装包或重新启动
                  pnpm dev 后的桌面窗口再开关。
                </n-text>
                <n-text v-if="hasDesktopApi() && !hasOpenAtLoginApi()" type="warning" style="font-size: 12px">
                  客户端进程偏旧，未加载自启动接口。请完全退出 Electron 后重新运行桌面端，或安装下方打包好的安装包。
                </n-text>
                <n-text v-else-if="!hasDesktopApi()" type="warning" style="font-size: 12px">
                  当前不是桌面客户端窗口（例如用浏览器打开了页面）。请打开打包安装后的「闲鱼管家」或 pnpm
                  dev 启动的 Electron 窗口。
                </n-text>
              </n-space>
            </n-form-item>
          </n-form>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="automation" tab="自动化中心">
        <n-card size="small" :loading="loading" style="margin-top: 8px">
          <n-text depth="3" style="display: block; margin-bottom: 12px; font-size: 12px">
            软件打开且账号在线时，每日擦亮 / 求评价会按设定时间执行。
          </n-text>
          <template v-if="autoForm">
            <n-form label-placement="left" label-width="160">
              <n-form-item label="付款后自动发货">
                <n-space vertical :size="4">
                  <n-switch v-model:value="autoForm.auto_confirm" />
                  <n-text depth="3" style="font-size: 12px"
                    >付款后先发卡密，成功后再确认发货（需在「发货模板」配置规则）</n-text
                  >
                </n-space>
              </n-form-item>
              <n-form-item label="拍下未付款自动改价">
                <n-space vertical :size="6">
                  <n-switch v-model:value="autoForm.unpaid_repricing" />
                  <n-space align="center">
                    <n-radio-group
                      v-model:value="autoForm.unpaid_markup_type"
                      name="unpaid_markup"
                      :disabled="!autoForm.unpaid_repricing"
                    >
                      <n-radio value="amount">加价金额 ¥</n-radio>
                      <n-radio value="percent">加价比例 %</n-radio>
                    </n-radio-group>
                    <n-input-number
                      v-model:value="autoForm.unpaid_markup_value"
                      :min="0"
                      :precision="2"
                      style="width: 140px"
                      :disabled="!autoForm.unpaid_repricing"
                    />
                  </n-space>
                  <n-space align="center">
                    <n-text depth="3">拍下后延迟</n-text>
                    <n-input-number
                      v-model:value="autoForm.unpaid_repricing_delay_sec"
                      :min="0"
                      :max="3600"
                      style="width: 100px"
                      :disabled="!autoForm.unpaid_repricing"
                    />
                    <n-text depth="3">秒再改价（默认 30，给买家留出付款窗口）</n-text>
                  </n-space>
                  <n-text depth="3" style="font-size: 12px">
                    真实功能：收到「我已拍下，待付款」后延迟改价。按拍下原价加价（如 +5 元或 +10%）。
                  </n-text>
                </n-space>
              </n-form-item>
              <n-form-item label="评价后发送赠品">
                <n-space vertical :size="4">
                  <n-switch v-model:value="autoForm.gift_after_review" />
                  <n-text depth="3" style="font-size: 12px">
                    真实功能：买家完成评价后走「发货模板/卡密库存」自动发卡。需先绑定对应商品的卡密，否则无内容可发。
                  </n-text>
                </n-space>
              </n-form-item>
              <n-form-item label="超时未评价求评价">
                <n-space vertical :size="6">
                  <n-switch v-model:value="autoForm.request_review" />
                  <n-space align="center">
                    <n-text depth="3">发货后</n-text>
                    <n-input-number
                      v-model:value="autoForm.request_review_hours"
                      :min="1"
                      :max="720"
                      style="width: 100px"
                      :disabled="!autoForm.request_review"
                    />
                    <n-text depth="3">小时未评价则发送</n-text>
                  </n-space>
                  <n-input
                    v-model:value="autoForm.request_review_text"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    placeholder="求评价文案"
                    :disabled="!autoForm.request_review"
                  />
                  <n-text depth="3" style="font-size: 12px">
                    真实功能：软件在线时定时扫描已发货未评价订单并私信求评。
                  </n-text>
                </n-space>
              </n-form-item>
              <n-form-item label="收货后自动评价">
                <n-space vertical :size="6">
                  <n-switch v-model:value="autoForm.auto_review" />
                  <n-input
                    v-model:value="autoForm.auto_review_text"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    placeholder="买家确认收货后自动发送的评价/感谢文案"
                    :disabled="!autoForm.auto_review"
                  />
                  <n-text depth="3" style="font-size: 12px">
                    真实功能：收到「买家确认收货」系统消息后，向该会话发送上方文案（引导/感谢，非平台官方评价接口）。
                  </n-text>
                </n-space>
              </n-form-item>
              <n-divider />
              <n-form-item label="每日自动擦亮">
                <n-space vertical :size="6">
                  <n-switch v-model:value="autoForm.daily_polish" />
                  <n-space align="center">
                    <n-text depth="3">每天</n-text>
                    <n-time-picker
                      v-model:value="polishTimeMs"
                      format="HH:mm"
                      :disabled="!autoForm.daily_polish"
                    />
                    <n-text depth="3">自动擦亮在架商品</n-text>
                  </n-space>
                  <n-text v-if="autoForm.last_polish_date" depth="3" style="font-size: 12px"
                    >上次擦亮日期：{{ autoForm.last_polish_date }}</n-text
                  >
                  <n-text depth="3" style="font-size: 12px">
                    真实功能：到达设定时刻且账号在线时调用擦亮接口；软件需保持打开。
                  </n-text>
                </n-space>
              </n-form-item>
              <n-divider />
              <n-form-item label="代发支付密码">
                <n-space vertical :size="4" style="width: 100%">
                  <n-input
                    v-model:value="autoForm.dropship_pay_password"
                    type="password"
                    show-password-on="click"
                    placeholder="可选；代采向上家购买时尝试自动填写"
                    style="max-width: 280px"
                  />
                  <n-text depth="3" style="font-size: 12px"
                    >仅用于卖家监控「代发」自动向上家购买。若提示密码错误：请核对是否为支付宝 6
                    位支付密码（非登录密码）；填错会被平台拦截，需到支付宝核对后重试。支付宝常仍需人工确认。</n-text
                  >
                </n-space>
              </n-form-item>
            </n-form>
            <n-button type="primary" :loading="savingAuto" @click="saveAuto">保存自动化规则</n-button>
          </template>
          <n-text v-else depth="3">请先选择账号</n-text>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="ai" tab="AI 助手">
        <n-card size="small" style="margin-top: 8px">
          <template v-if="aiForm">
            <n-form label-placement="left" label-width="160">
              <n-form-item label="启用 AI 自动回复">
                <n-switch v-model:value="aiForm.ai_enabled" />
              </n-form-item>
              <n-form-item label="最大折扣比例 (%)">
                <n-input-number v-model:value="aiForm.max_discount_percent" :min="0" :max="100" />
              </n-form-item>
              <n-form-item label="最大折扣金额 (元)">
                <n-input-number v-model:value="aiForm.max_discount_amount" :min="0" />
              </n-form-item>
              <n-form-item label="最大砍价轮次">
                <n-input-number v-model:value="aiForm.max_bargain_rounds" :min="1" :max="20" />
              </n-form-item>
              <n-form-item label="模型 / Base URL">
                <n-space vertical style="width: 100%">
                  <n-input v-model:value="aiForm.model_name" placeholder="如 qwen-plus / qwen2.5" />
                  <n-input v-model:value="aiForm.base_url" placeholder="兼容 OpenAI 的 Base URL" />
                  <n-text depth="3" style="font-size: 12px">
                    没有内置免费云模型。可用本机 Ollama（免费）：Base URL 填
                    http://127.0.0.1:11434/v1 ，模型填已拉取的名称，API Key 可随便填 ollama。
                  </n-text>
                </n-space>
              </n-form-item>
              <n-form-item label="API Key">
                <n-input v-model:value="aiForm.api_key" type="password" show-password-on="click" />
              </n-form-item>
              <n-form-item label="自定义提示词">
                <n-input
                  v-model:value="aiForm.custom_prompts"
                  type="textarea"
                  :autosize="{ minRows: 3, maxRows: 6 }"
                />
              </n-form-item>
            </n-form>
            <n-space>
              <n-button type="primary" :loading="savingAi" @click="saveAi">保存 AI 设置</n-button>
              <n-button secondary :loading="testingAi" @click="onTestAi">测试连接</n-button>
            </n-space>
          </template>
          <n-text v-else depth="3">请先选择账号</n-text>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="schedule" tab="定时调度">
        <n-card size="small" style="margin-top: 8px">
          <n-text depth="3" style="display: block; margin-bottom: 12px; font-size: 12px">
            日常擦亮在「自动化中心」按时执行；下面是手动批量入口说明。
          </n-text>
          <n-space vertical>
            <n-text>每日自动擦亮：自动化中心开启并设定时间（账号需在线）</n-text>
            <n-text>批量擦亮 / 批量改价：商品管理勾选后点按钮立即执行</n-text>
            <n-text>卖家跟价 / 跟下架 / 代发：营销管理 → 卖家监控</n-text>
            <n-text>代发任务状态：卖家监控页底部「代发任务」</n-text>
          </n-space>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="password" tab="修改密码">
        <n-card size="small" style="margin-top: 8px; max-width: 420px">
          <n-form>
            <n-form-item label="当前密码">
              <n-input v-model:value="pwd.current" type="password" show-password-on="click" />
            </n-form-item>
            <n-form-item label="新密码">
              <n-input v-model:value="pwd.next" type="password" show-password-on="click" />
            </n-form-item>
            <n-form-item label="确认新密码">
              <n-input v-model:value="pwd.confirm" type="password" show-password-on="click" />
            </n-form-item>
          </n-form>
          <n-button type="primary" @click="onChangePwd">修改密码</n-button>
        </n-card>
      </n-tab-pane>
    </n-tabs>
  </n-space>
</template>
