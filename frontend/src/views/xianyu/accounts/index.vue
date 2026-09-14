<template>
  <div class="art-full-height p-4">
    <div class="art-card p-5 mb-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span class="font-medium text-g-900">闲鱼账号</span>
          <span class="text-xs text-g-500 ml-3" v-if="abnormalCount">
            {{ abnormalCount }} 个账号异常，请及时处理
          </span>
        </div>
        <ElSpace>
          <ElButton type="primary" @click="openQrLogin()">扫码添加</ElButton>
          <ElButton @click="openCookieDialog()">Cookie 添加</ElButton>
          <ElButton :loading="loading" @click="loadData">刷新</ElButton>
        </ElSpace>
      </div>
    </div>

    <ElRow :gutter="16" v-loading="loading">
      <ElCol :xs="24" :sm="12" :lg="8" v-for="row in list" :key="row.id" class="mb-4">
        <div class="art-card p-5 h-full" :class="{ 'is-abnormal': row.health_status === 'abnormal' }">
          <div class="flex items-start gap-3 mb-4">
            <ElAvatar :size="52" :src="row.avatar_url" />
            <div class="min-w-0 flex-1">
              <div class="font-semibold text-g-900 truncate">
                {{ row.nickname || row.tracknick || row.id }}
              </div>
              <div
                class="text-xs text-g-500 truncate mt-0.5"
                v-if="row.remark && row.remark !== row.nickname"
              >
                备注: {{ row.remark }}
              </div>
              <div class="text-xs text-g-500 font-mono truncate mt-0.5">账号ID: {{ row.id }}</div>
              <div class="text-xs text-g-500 truncate mt-0.5" v-if="row.unb">闲鱼号: {{ row.unb }}</div>
            </div>
            <ElSwitch :model-value="row.enabled" @change="(v) => toggleEnabled(row.id, !!v)" />
          </div>

          <div class="flex flex-wrap gap-2 mb-3">
            <ElTag
              :type="row.health_status === 'normal' ? 'success' : 'danger'"
              size="small"
              effect="dark"
            >
              {{ row.health_status === 'normal' ? '正常' : '异常' }}
            </ElTag>
            <ElTag :type="row.online ? 'success' : 'info'" size="small" effect="light">
              {{ row.online ? '在线聊天中' : '未连接' }}
            </ElTag>
            <ElTag :type="row.enabled ? 'success' : 'info'" size="small" effect="plain">
              {{ row.enabled ? '已启用' : '已禁用' }}
            </ElTag>
            <ElTag v-if="row.ai_enabled" type="warning" size="small">AI 议价</ElTag>
            <ElTag v-if="row.auto_confirm" type="primary" size="small">自动确认</ElTag>
          </div>

          <ElAlert
            v-if="row.health_status === 'abnormal'"
            class="mb-3"
            type="error"
            :closable="false"
            :title="row.health_reason || '账号异常，请重新登录或重连'"
            show-icon
          />

          <ElForm label-position="top" size="small">
            <ElFormItem label="备注（仅本地，不影响闲鱼昵称）">
              <ElInput
                :model-value="row.remark"
                placeholder="可选备注"
                @change="(v: string) => saveRemark(row.id, v)"
              />
            </ElFormItem>
          </ElForm>

          <div class="flex gap-2 flex-wrap">
            <ElButton
              v-if="row.health_status === 'abnormal'"
              size="small"
              type="warning"
              :loading="row._reconnecting"
              @click="reconnect(row)"
            >
              快捷重连
            </ElButton>
            <ElButton size="small" type="primary" @click="openQrLogin(row.id)">扫码重登</ElButton>
            <ElButton size="small" @click="openCookieDialog(row)">更新 Cookie</ElButton>
            <ElButton size="small" :loading="row._refreshing" @click="refreshProfile(row)">
              刷新资料
            </ElButton>
            <ElButton size="small" type="primary" plain @click="openAi(row.id)">AI 议价</ElButton>
            <ElButton size="small" type="danger" plain @click="remove(row.id)">删除</ElButton>
          </div>
        </div>
      </ElCol>
    </ElRow>

    <ElEmpty v-if="!loading && !list.length" description="暂无账号，请扫码或 Cookie 添加" />

    <ElDialog v-model="qrVisible" title="扫码登录" width="420px">
      <div class="text-center" v-loading="qrLoading">
        <img v-if="qrUrl" :src="qrUrl" alt="qr" class="mx-auto max-w-[240px]" />
        <p class="mt-3 text-sm text-gray-500">请使用闲鱼 App 扫码</p>
        <p class="text-xs text-gray-400" v-if="reloginTarget">将更新账号：{{ reloginTarget }}</p>
        <p class="text-xs text-gray-400">状态：{{ qrStatus }}</p>
      </div>
    </ElDialog>

    <ElDialog v-model="cookieVisible" :title="cookieForm.id ? '更新 / 添加 Cookie' : '手动添加 Cookie'" width="520px">
      <ElForm label-width="80px">
        <ElFormItem label="账号ID">
          <ElInput v-model="cookieForm.id" placeholder="建议用 unb / 用户ID" :disabled="!!reloginTarget" />
        </ElFormItem>
        <ElFormItem label="Cookie">
          <ElInput v-model="cookieForm.cookie" type="textarea" :rows="5" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="cookieVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveCookie">保存</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="aiVisible" title="AI 议价设置" width="560px">
      <ElForm label-width="120px" v-if="aiForm">
        <ElFormItem label="启用 AI"><ElSwitch v-model="aiForm.ai_enabled" /></ElFormItem>
        <ElFormItem label="模型"><ElInput v-model="aiForm.model_name" /></ElFormItem>
        <ElFormItem label="API Key">
          <ElInput v-model="aiForm.api_key" type="password" show-password />
        </ElFormItem>
        <ElFormItem label="Base URL"><ElInput v-model="aiForm.base_url" /></ElFormItem>
        <ElFormItem label="最大折扣%">
          <ElInputNumber v-model="aiForm.max_discount_percent" :min="0" :max="100" />
        </ElFormItem>
        <ElFormItem label="最大减免额">
          <ElInputNumber v-model="aiForm.max_discount_amount" :min="0" />
        </ElFormItem>
        <ElFormItem label="议价轮数">
          <ElInputNumber v-model="aiForm.max_bargain_rounds" :min="1" />
        </ElFormItem>
        <ElFormItem label="自定义提示">
          <ElInput v-model="aiForm.custom_prompts" type="textarea" :rows="3" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="testAi">测试连接</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveAi">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import {
    getAccountDetails,
    updateAccountStatus,
    updateAccountRemark,
    updateAccountCookie,
    deleteAccount,
    addAccount,
    generateQRLogin,
    checkQRLoginStatus,
    getAIReplySettings,
    updateAIReplySettings,
    testAIConnection,
    getAllAISettings,
    refreshAccountProfile,
    reconnectAccount,
    type AccountDetail,
    type AIReplySettings
  } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'Accounts' })

  type AccountRow = AccountDetail & { _refreshing?: boolean; _reconnecting?: boolean }

  const loading = ref(false)
  const saving = ref(false)
  const list = ref<AccountRow[]>([])
  const abnormalCount = computed(
    () => list.value.filter((a) => a.health_status === 'abnormal').length
  )

  const qrVisible = ref(false)
  const qrLoading = ref(false)
  const qrUrl = ref('')
  const qrStatus = ref('')
  const reloginTarget = ref('')
  let qrTimer: ReturnType<typeof setInterval> | null = null

  const cookieVisible = ref(false)
  const cookieForm = reactive({ id: '', cookie: '' })

  const aiVisible = ref(false)
  const aiCookieId = ref('')
  const aiForm = ref<AIReplySettings | null>(null)

  async function loadData() {
    loading.value = true
    try {
      const [accounts, aiMap] = await Promise.all([
        getAccountDetails(),
        getAllAISettings().catch(() => ({} as Record<string, AIReplySettings>))
      ])
      list.value = accounts.map((a) => ({
        ...a,
        ai_enabled: aiMap[a.id]?.ai_enabled ?? false
      }))
    } finally {
      loading.value = false
    }
  }

  async function toggleEnabled(id: string, enabled: boolean) {
    await updateAccountStatus(id, enabled)
    ElMessage.success(enabled ? '已启用' : '已禁用')
    loadData()
  }

  async function saveRemark(id: string, remark: string) {
    await updateAccountRemark(id, remark || '')
    ElMessage.success('备注已保存')
    loadData()
  }

  async function reconnect(row: AccountRow) {
    row._reconnecting = true
    try {
      const res = await reconnectAccount(row.id)
      ElMessage.success(res?.message || '已触发重连')
      setTimeout(loadData, 1500)
    } catch (e: any) {
      ElMessage.error(e?.message || '重连失败')
    } finally {
      row._reconnecting = false
    }
  }

  async function refreshProfile(row: AccountRow) {
    row._refreshing = true
    try {
      const res = await refreshAccountProfile(row.id)
      if (res?.success) {
        ElMessage.success(`已更新：${res.nickname || '昵称'}`)
      } else {
        ElMessage.warning(res?.message || '资料刷新失败，请确认 Cookie 有效')
      }
      await loadData()
    } catch (e: any) {
      ElMessage.error(e?.message || '刷新失败')
    } finally {
      row._refreshing = false
    }
  }

  async function remove(id: string) {
    await ElMessageBox.confirm(`确认删除账号 ${id}？`, '提示', { type: 'warning' })
    await deleteAccount(id)
    ElMessage.success('已删除')
    loadData()
  }

  async function openQrLogin(targetId = '') {
    reloginTarget.value = targetId
    qrVisible.value = true
    qrLoading.value = true
    qrStatus.value = '生成中'
    try {
      const res = await generateQRLogin()
      qrUrl.value = res.qr_code_url || ''
      qrStatus.value = '等待扫码'
      if (qrTimer) clearInterval(qrTimer)
      if (res.session_id) {
        qrTimer = setInterval(async () => {
          const st = (await checkQRLoginStatus(res.session_id!)) as Record<string, any>
          qrStatus.value = st.status || st.message || JSON.stringify(st)
          if (st.success || st.status === 'success') {
            if (qrTimer) clearInterval(qrTimer)
            ElMessage.success(targetId ? '重登成功' : '添加成功')
            qrVisible.value = false
            loadData()
          }
        }, 2000)
      }
    } finally {
      qrLoading.value = false
    }
  }

  function openCookieDialog(row?: AccountRow) {
    reloginTarget.value = row?.id || ''
    cookieForm.id = row?.id || ''
    cookieForm.cookie = ''
    cookieVisible.value = true
  }

  async function saveCookie() {
    if (!cookieForm.id || !cookieForm.cookie) {
      ElMessage.warning('请填写完整')
      return
    }
    saving.value = true
    try {
      if (reloginTarget.value) {
        await updateAccountCookie(cookieForm.id, cookieForm.cookie)
        await reconnectAccount(cookieForm.id).catch(() => undefined)
        ElMessage.success('Cookie 已更新并尝试重连')
      } else {
        await addAccount({ id: cookieForm.id, cookie: cookieForm.cookie })
        ElMessage.success('添加成功')
      }
      cookieVisible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  async function openAi(id: string) {
    aiCookieId.value = id
    aiForm.value = await getAIReplySettings(id)
    aiVisible.value = true
  }

  async function saveAi() {
    if (!aiForm.value) return
    saving.value = true
    try {
      await updateAIReplySettings(aiCookieId.value, aiForm.value)
      ElMessage.success('已保存')
      aiVisible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  async function testAi() {
    const res = await testAIConnection(aiCookieId.value)
    ElMessage[res.success ? 'success' : 'error'](res.message || '')
  }

  onMounted(loadData)
  onBeforeUnmount(() => {
    if (qrTimer) clearInterval(qrTimer)
  })
</script>

<style scoped>
  .is-abnormal {
    border: 1px solid var(--el-color-danger-light-5);
    box-shadow: 0 0 0 1px rgba(245, 108, 108, 0.08);
  }
</style>
