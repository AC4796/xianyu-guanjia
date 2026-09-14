<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">系统设置</span>
          <ElButton :loading="loading" @click="loadData">刷新</ElButton>
        </div>
      </template>

      <ElTabs>
        <ElTabPane label="基础设置">
          <ElForm label-width="160px" class="max-w-xl" v-loading="loading">
            <ElFormItem label="开放注册">
              <ElSwitch v-model="settings.registration_enabled" />
            </ElFormItem>
            <ElFormItem label="登录验证码">
              <ElSwitch v-model="settings.login_captcha_enabled" />
            </ElFormItem>
            <ElFormItem label="显示默认登录信息">
              <ElSwitch v-model="settings.show_default_login_info" />
            </ElFormItem>
            <ElFormItem>
              <ElButton type="primary" :loading="saving" @click="saveSettings">保存设置</ElButton>
            </ElFormItem>
          </ElForm>
        </ElTabPane>
        <ElTabPane label="修改密码">
          <ElForm label-width="120px" class="max-w-md">
            <ElFormItem label="当前密码">
              <ElInput v-model="pwd.current" type="password" show-password />
            </ElFormItem>
            <ElFormItem label="新密码">
              <ElInput v-model="pwd.next" type="password" show-password />
            </ElFormItem>
            <ElFormItem>
              <ElButton type="primary" :loading="saving" @click="savePwd">修改密码</ElButton>
            </ElFormItem>
          </ElForm>
        </ElTabPane>
      </ElTabs>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { getSystemSettings, updateSystemSettings, changePassword } from '@/api/xy'
  import { ElMessage } from 'element-plus'

  defineOptions({ name: 'XySettings' })

  const loading = ref(false)
  const saving = ref(false)
  const settings = reactive({
    registration_enabled: false,
    login_captcha_enabled: true,
    show_default_login_info: true
  })
  const pwd = reactive({ current: '', next: '' })

  function toBool(v: unknown) {
    return v === true || v === 'true' || v === 1 || v === '1'
  }

  async function loadData() {
    loading.value = true
    try {
      const data = await getSystemSettings()
      settings.registration_enabled = toBool(data.registration_enabled)
      settings.login_captcha_enabled = toBool(data.login_captcha_enabled)
      settings.show_default_login_info = toBool(data.show_default_login_info)
    } finally {
      loading.value = false
    }
  }

  async function saveSettings() {
    saving.value = true
    try {
      await updateSystemSettings({
        registration_enabled: settings.registration_enabled,
        login_captcha_enabled: settings.login_captcha_enabled,
        show_default_login_info: settings.show_default_login_info
      })
      ElMessage.success('已保存')
    } finally {
      saving.value = false
    }
  }

  async function savePwd() {
    if (!pwd.current || !pwd.next) {
      ElMessage.warning('请填写完整')
      return
    }
    saving.value = true
    try {
      const res = await changePassword(pwd.current, pwd.next)
      ElMessage[res.success ? 'success' : 'error'](res.message || '完成')
      if (res.success) {
        pwd.current = ''
        pwd.next = ''
      }
    } finally {
      saving.value = false
    }
  }

  onMounted(loadData)
</script>
