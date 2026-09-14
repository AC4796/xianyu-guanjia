<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns
} from 'naive-ui'
import {
  createNotificationChannel,
  deleteNotificationChannel,
  getNotificationChannels,
  testNotificationChannel,
  type NotificationChannel
} from '../api/system'

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const saving = ref(false)
const rows = ref<NotificationChannel[]>([])
const showModal = ref(false)

const form = ref({
  name: '',
  type: 'webhook',
  webhook_url: '',
  secret: '',
  device_key: '',
  server_url: '',
  smtp_server: '',
  smtp_port: 465,
  email_user: '',
  email_password: '',
  recipient_email: '',
  bot_token: '',
  chat_id: ''
})

const typeOptions = [
  { label: '自定义 Webhook', value: 'webhook' },
  { label: '钉钉机器人', value: 'dingtalk' },
  { label: '飞书机器人', value: 'feishu' },
  { label: '企业微信机器人', value: 'wechat' },
  { label: 'Bark（iOS）', value: 'bark' },
  { label: '邮箱 SMTP', value: 'email' },
  { label: 'Telegram Bot', value: 'telegram' }
]

const typeHint = computed(() => {
  const t = form.value.type
  const map: Record<string, string> = {
    webhook:
      '如何获取：准备任意可接收 POST JSON 的 HTTP 地址（自建服务 / RequestBin / 云函数）。将完整 URL 填入 Webhook。',
    dingtalk:
      '如何获取：钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义 → 复制 Webhook。若开启「加签」，把 Secret 一并填写。',
    feishu:
      '如何获取：飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人 → 复制 Webhook 地址填入。',
    wechat:
      '如何获取：企业微信群 → 添加群机器人 → 新建 → 复制 Webhook 地址填入（以 qyapi.weixin.qq.com 开头）。',
    bark:
      '如何获取：① iPhone 安装 Bark App；② 打开 App 复制 Device Key；③ 官方推送填 Server 留空即可，自建则填 https://你的域名。',
    email:
      '如何获取：① 邮箱开启 SMTP（QQ：设置→账户→开启 SMTP，生成授权码）；② 填 SMTP 服务器/端口/发件邮箱/授权码（不是登录密码）/收件邮箱。',
    telegram:
      '如何获取：① Telegram 找 @BotFather → /newbot 拿到 bot_token；② 把机器人拉进群或私聊一次；③ 访问 https://api.telegram.org/bot<token>/getUpdates 查 chat.id 填入 chat_id。'
  }
  return map[t] || ''
})

const columns: DataTableColumns<NotificationChannel> = [
  { title: '名称', key: 'name' },
  { title: '类型', key: 'type', width: 110 },
  {
    title: '启用',
    key: 'enabled',
    width: 80,
    render: (r) => (r.enabled === false ? '否' : '是')
  },
  {
    title: '操作',
    key: 'a',
    width: 160,
    render: (r) =>
      h(NSpace, null, () => [
        h(
          NButton,
          {
            size: 'tiny',
            onClick: async () => {
              try {
                await testNotificationChannel(r.id)
                message.success('测试已发送')
              } catch (e: any) {
                message.error(e?.message || '测试失败')
              }
            }
          },
          () => '测试'
        ),
        h(
          NButton,
          {
            size: 'tiny',
            type: 'error',
            secondary: true,
            onClick: () => {
              dialog.warning({
                title: '删除渠道',
                content: `确定删除「${r.name}」吗？`,
                positiveText: '删除',
                negativeText: '取消',
                onPositiveClick: async () => {
                  await deleteNotificationChannel(r.id)
                  message.success('已删除')
                  await load()
                }
              })
            }
          },
          () => '删除'
        )
      ])
  }
]

function resetForm(): void {
  form.value = {
    name: '',
    type: 'webhook',
    webhook_url: '',
    secret: '',
    device_key: '',
    server_url: '',
    smtp_server: '',
    smtp_port: 465,
    email_user: '',
    email_password: '',
    recipient_email: '',
    bot_token: '',
    chat_id: ''
  }
}

function buildConfig(): Record<string, unknown> {
  const t = form.value.type
  if (t === 'email') {
    return {
      smtp_server: form.value.smtp_server.trim(),
      smtp_port: Number(form.value.smtp_port) || 465,
      email_user: form.value.email_user.trim(),
      email_password: form.value.email_password,
      recipient_email: form.value.recipient_email.trim()
    }
  }
  if (t === 'bark') {
    return {
      device_key: form.value.device_key.trim(),
      server_url: form.value.server_url.trim() || undefined
    }
  }
  if (t === 'telegram') {
    return {
      bot_token: form.value.bot_token.trim(),
      chat_id: form.value.chat_id.trim()
    }
  }
  // webhook / dingtalk / feishu / wechat
  const cfg: Record<string, unknown> = {
    webhook_url: form.value.webhook_url.trim()
  }
  if (t === 'dingtalk' && form.value.secret.trim()) {
    cfg.secret = form.value.secret.trim()
  }
  return cfg
}

function validate(): string | null {
  const t = form.value.type
  if (!form.value.name.trim()) return '请输入名称'
  if (t === 'email') {
    if (!form.value.smtp_server.trim()) return '请填写 SMTP 服务器'
    if (!form.value.email_user.trim()) return '请填写发件邮箱账号'
    if (!form.value.email_password) return '请填写邮箱授权码/密码'
    if (!form.value.recipient_email.trim()) return '请填写收件邮箱'
  } else if (t === 'bark') {
    if (!form.value.device_key.trim()) return '请填写 Bark Device Key'
  } else if (t === 'telegram') {
    if (!form.value.bot_token.trim()) return '请填写 Bot Token'
    if (!form.value.chat_id.trim()) return '请填写 Chat ID'
  } else if (!form.value.webhook_url.trim()) {
    return '请填写 Webhook 地址'
  }
  return null
}

async function load(): Promise<void> {
  loading.value = true
  try {
    rows.value = await getNotificationChannels()
  } catch (e: any) {
    message.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  const err = validate()
  if (err) {
    message.warning(err)
    return
  }
  saving.value = true
  try {
    await createNotificationChannel({
      name: form.value.name.trim(),
      type: form.value.type,
      config: buildConfig()
    })
    message.success('已创建通知渠道')
    showModal.value = false
    resetForm()
    await load()
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <n-card title="通知设置" size="small">
    <n-text depth="3" style="display: block; margin-bottom: 12px; font-size: 12px">
      按渠道类型填写对应字段（邮箱/钉钉/飞书等配置不同）。保存后可点「测试」验证是否真实可达。
    </n-text>
    <n-space style="margin-bottom: 12px">
      <n-button
        type="primary"
        @click="
          () => {
            resetForm()
            showModal = true
          }
        "
      >
        添加通知渠道
      </n-button>
    </n-space>
    <n-data-table :loading="loading" :columns="columns" :data="rows" size="small" />
  </n-card>

  <n-modal v-model:show="showModal" preset="card" title="添加通知渠道" style="width: 520px">
    <n-form label-placement="left" label-width="110">
      <n-form-item label="名称">
        <n-input v-model:value="form.name" placeholder="如：钉钉业务群 / 邮箱告警" />
      </n-form-item>
      <n-form-item label="类型">
        <n-select v-model:value="form.type" :options="typeOptions" />
      </n-form-item>
      <n-text depth="3" style="display: block; margin: -6px 0 12px 110px; font-size: 12px">
        {{ typeHint }}
      </n-text>

      <template v-if="['webhook', 'dingtalk', 'feishu', 'wechat'].includes(form.type)">
        <n-form-item label="Webhook 地址" required>
          <n-input v-model:value="form.webhook_url" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" />
        </n-form-item>
        <n-form-item v-if="form.type === 'dingtalk'" label="加签 Secret">
          <n-input v-model:value="form.secret" placeholder="可选，开启加签时填写" />
        </n-form-item>
      </template>

      <template v-else-if="form.type === 'bark'">
        <n-form-item label="Device Key" required>
          <n-input v-model:value="form.device_key" />
        </n-form-item>
        <n-form-item label="Server URL">
          <n-input v-model:value="form.server_url" placeholder="可选，默认官方 https://api.day.app" />
        </n-form-item>
      </template>

      <template v-else-if="form.type === 'email'">
        <n-form-item label="SMTP 服务器" required>
          <n-input v-model:value="form.smtp_server" placeholder="如 smtp.qq.com / smtp.163.com" />
        </n-form-item>
        <n-form-item label="SMTP 端口">
          <n-input-number v-model:value="form.smtp_port" :min="1" :max="65535" style="width: 140px" />
        </n-form-item>
        <n-form-item label="发件账号" required>
          <n-input v-model:value="form.email_user" placeholder="完整邮箱地址" />
        </n-form-item>
        <n-form-item label="授权码" required>
          <n-input
            v-model:value="form.email_password"
            type="password"
            show-password-on="click"
            placeholder="邮箱 SMTP 授权码（非登录密码）"
          />
        </n-form-item>
        <n-form-item label="收件邮箱" required>
          <n-input v-model:value="form.recipient_email" />
        </n-form-item>
      </template>

      <template v-else-if="form.type === 'telegram'">
        <n-form-item label="Bot Token" required>
          <n-input v-model:value="form.bot_token" />
        </n-form-item>
        <n-form-item label="Chat ID" required>
          <n-input v-model:value="form.chat_id" />
        </n-form-item>
      </template>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showModal = false">取消</n-button>
        <n-button type="primary" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
