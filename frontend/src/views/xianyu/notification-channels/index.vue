<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">通知渠道</span>
          <ElSpace>
            <ElButton type="primary" @click="openEdit()">新增渠道</ElButton>
            <ElButton :loading="loading" @click="loadData">刷新</ElButton>
          </ElSpace>
        </div>
      </template>
      <ElTable :data="list" v-loading="loading" stripe border>
        <ElTableColumn prop="name" label="名称" min-width="140" />
        <ElTableColumn prop="type" label="类型" width="120" />
        <ElTableColumn label="启用" width="90">
          <template #default="{ row }">
            <ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton link @click="test(row.id)">测试</ElButton>
            <ElButton link type="danger" @click="remove(row.id)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog v-model="visible" :title="form.id ? '编辑渠道' : '新增渠道'" width="560px">
      <ElForm label-width="90px">
        <ElFormItem label="名称"><ElInput v-model="form.name" /></ElFormItem>
        <ElFormItem label="类型">
          <ElSelect v-model="form.type">
            <ElOption label="钉钉" value="dingtalk" />
            <ElOption label="飞书" value="feishu" />
            <ElOption label="Bark" value="bark" />
            <ElOption label="邮箱" value="email" />
            <ElOption label="Webhook" value="webhook" />
            <ElOption label="Telegram" value="telegram" />
            <ElOption label="微信" value="wechat" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="配置JSON">
          <ElInput v-model="configText" type="textarea" :rows="6" placeholder='{"url":"..."}' />
        </ElFormItem>
        <ElFormItem label="启用"><ElSwitch v-model="form.enabled" /></ElFormItem>
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
    getNotificationChannels,
    createNotificationChannel,
    updateNotificationChannel,
    deleteNotificationChannel,
    testNotificationChannel,
    type NotificationChannel
  } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'NotificationChannels' })

  const loading = ref(false)
  const saving = ref(false)
  const list = ref<NotificationChannel[]>([])
  const visible = ref(false)
  const configText = ref('{}')
  const form = reactive<Partial<NotificationChannel>>({
    name: '',
    type: 'dingtalk',
    enabled: true
  })

  async function loadData() {
    loading.value = true
    try {
      const res = await getNotificationChannels()
      list.value = res.data || []
    } finally {
      loading.value = false
    }
  }

  function openEdit(row?: NotificationChannel) {
    Object.assign(form, {
      id: undefined,
      name: '',
      type: 'dingtalk',
      enabled: true,
      ...row
    })
    configText.value = JSON.stringify(row?.config || {}, null, 2)
    visible.value = true
  }

  async function save() {
    let config: Record<string, unknown> = {}
    try {
      config = JSON.parse(configText.value || '{}')
    } catch {
      ElMessage.error('配置 JSON 无效')
      return
    }
    if (!form.name || !form.type) {
      ElMessage.warning('请填写完整')
      return
    }
    saving.value = true
    try {
      if (form.id) {
        await updateNotificationChannel(form.id, {
          name: form.name,
          config,
          enabled: form.enabled
        })
      } else {
        await createNotificationChannel({
          name: form.name!,
          type: form.type!,
          config
        })
      }
      ElMessage.success('已保存')
      visible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  async function test(id: string) {
    await testNotificationChannel(id)
    ElMessage.success('已发送测试')
  }

  async function remove(id: string) {
    await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
    await deleteNotificationChannel(id)
    ElMessage.success('已删除')
    loadData()
  }

  onMounted(loadData)
</script>
