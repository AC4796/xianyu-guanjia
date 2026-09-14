<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">账号消息通知</span>
          <ElButton type="primary" @click="openBind">绑定通知</ElButton>
        </div>
      </template>
      <ElTable :data="list" v-loading="loading" stripe border>
        <ElTableColumn label="账号" min-width="180">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <ElAvatar :size="24" :src="accountAvatar(row.cookie_id)" />
              <div>
                <div>{{ accountName(row.cookie_id) }}</div>
                <div class="text-xs text-g-400">{{ row.cookie_id }}</div>
              </div>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="channel_name" label="渠道" min-width="140" />
        <ElTableColumn prop="channel_id" label="渠道ID" width="100" />
        <ElTableColumn label="启用" width="90">
          <template #default="{ row }">
            <ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="120">
          <template #default="{ row }">
            <ElButton link type="danger" @click="removeAccount(row.cookie_id)">清除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog v-model="visible" title="绑定账号通知" width="480px">
      <ElForm label-width="90px">
        <ElFormItem label="账号">
          <ElSelect v-model="bind.cookie_id" style="width: 100%">
            <ElOption
              v-for="a in accounts"
              :key="a.id"
              :label="a.nickname || a.remark || a.id"
              :value="a.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="渠道">
          <ElSelect v-model="bind.channel_id" style="width: 100%">
            <ElOption
              v-for="c in channels"
              :key="c.id"
              :label="c.name"
              :value="Number(c.id)"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="启用"><ElSwitch v-model="bind.enabled" /></ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="visible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import {
    getMessageNotifications,
    setMessageNotification,
    deleteAccountNotifications,
    getNotificationChannels,
    getAccountDetails,
    type MessageNotification,
    type NotificationChannel
  } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'MessageNotifications' })

  const loading = ref(false)
  const saving = ref(false)
  const list = ref<MessageNotification[]>([])
  const accounts = ref<
    Array<{ id: string; remark?: string; nickname?: string; avatar_url?: string }>
  >([])
  const channels = ref<NotificationChannel[]>([])
  const visible = ref(false)
  const bind = reactive({ cookie_id: '', channel_id: 0, enabled: true })

  const accountMap = computed(() => {
    const m: Record<string, (typeof accounts.value)[0]> = {}
    accounts.value.forEach((a) => {
      m[a.id] = a
    })
    return m
  })

  function accountName(id?: string) {
    if (!id) return '-'
    const a = accountMap.value[id]
    return a?.nickname || a?.remark || id
  }

  function accountAvatar(id?: string) {
    if (!id) return ''
    return (
      accountMap.value[id]?.avatar_url ||
      `https://api.dicebear.com/7.x/avataaars/svg?seed=${id}`
    )
  }

  async function loadData() {
    loading.value = true
    try {
      const [msg, ch, acc] = await Promise.all([
        getMessageNotifications(),
        getNotificationChannels(),
        getAccountDetails()
      ])
      list.value = msg.data || []
      channels.value = ch.data || []
      accounts.value = acc
    } finally {
      loading.value = false
    }
  }

  function openBind() {
    bind.cookie_id = accounts.value[0]?.id || ''
    bind.channel_id = Number(channels.value[0]?.id || 0)
    bind.enabled = true
    visible.value = true
  }

  async function save() {
    if (!bind.cookie_id || !bind.channel_id) {
      ElMessage.warning('请选择账号和渠道')
      return
    }
    saving.value = true
    try {
      await setMessageNotification(bind.cookie_id, bind.channel_id, bind.enabled)
      ElMessage.success('已保存')
      visible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  async function removeAccount(cookieId: string) {
    await ElMessageBox.confirm('清除该账号全部通知绑定？', '提示', { type: 'warning' })
    await deleteAccountNotifications(cookieId)
    ElMessage.success('已清除')
    loadData()
  }

  onMounted(loadData)
</script>
