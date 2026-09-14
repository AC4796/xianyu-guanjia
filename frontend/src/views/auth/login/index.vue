<!-- 登录页面 -->
<template>
  <div class="flex w-full h-screen">
    <LoginLeftView />

    <div class="relative flex-1">
      <AuthTopBar />

      <div class="auth-right-wrap">
        <div class="form">
          <h3 class="title">闲鱼管家</h3>
          <p class="sub-title">智能自动发货与管理平台</p>

          <ElAlert
            v-if="needsInit"
            class="mt-4"
            type="warning"
            :closable="false"
            title="系统尚未初始化"
            description="请运行 启动.bat 或执行 python ensure_admin.py"
          />

          <ElForm
            v-else
            ref="formRef"
            :model="formData"
            :rules="rules"
            :key="formKey"
            @keyup.enter="handleSubmit"
            style="margin-top: 25px"
          >
            <ElFormItem prop="username">
              <ElInput
                class="custom-height"
                placeholder="管理员账号"
                v-model.trim="formData.username"
              />
            </ElFormItem>
            <ElFormItem prop="password">
              <ElInput
                class="custom-height"
                placeholder="密码"
                v-model.trim="formData.password"
                type="password"
                autocomplete="off"
                show-password
              />
            </ElFormItem>

            <div class="relative pb-5 mt-6">
              <div
                class="relative z-[2] overflow-hidden select-none rounded-lg border border-transparent tad-300"
                :class="{ '!border-[#FF4E4F]': !isPassing && isClickPass }"
              >
                <ArtDragVerify
                  ref="dragVerify"
                  v-model:value="isPassing"
                  :text="$t('login.sliderText')"
                  textColor="var(--art-gray-700)"
                  :successText="$t('login.sliderSuccessText')"
                  progressBarBg="var(--main-color)"
                  :background="isDark ? '#26272F' : '#F1F1F4'"
                  handlerBg="var(--default-box-color)"
                />
              </div>
              <p
                class="absolute top-0 z-[1] px-px mt-2 text-xs text-[#f56c6c] tad-300"
                :class="{ 'translate-y-10': !isPassing && isClickPass }"
              >
                {{ $t('login.placeholder.slider') }}
              </p>
            </div>

            <div class="flex-cb mt-2 text-sm">
              <ElCheckbox v-model="formData.rememberPassword">记住账号密码</ElCheckbox>
            </div>

            <div style="margin-top: 30px">
              <ElButton
                class="w-full custom-height"
                type="primary"
                @click="handleSubmit"
                :loading="loading"
                v-ripple
              >
                立即登录
              </ElButton>
            </div>
          </ElForm>

          <ElButton v-if="needsInit" class="mt-4 w-full" @click="checkInit">我已初始化，刷新</ElButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import AppConfig from '@/config'
  import { useUserStore } from '@/store/modules/user'
  import { useI18n } from 'vue-i18n'
  import { HttpError } from '@/utils/http/error'
  import { fetchLogin, fetchVerifySession } from '@/api/auth'
  import { ElMessage, ElNotification, type FormInstance, type FormRules } from 'element-plus'
  import { useSettingStore } from '@/store/modules/setting'

  defineOptions({ name: 'Login' })

  const REMEMBER_KEY = 'xy_login_remember'

  const settingStore = useSettingStore()
  const { isDark } = storeToRefs(settingStore)
  const { t, locale } = useI18n()
  const formKey = ref(0)
  const needsInit = ref(false)

  watch(locale, () => {
    formKey.value++
  })

  const dragVerify = ref()
  const userStore = useUserStore()
  const router = useRouter()
  const route = useRoute()
  const isPassing = ref(false)
  const isClickPass = ref(false)
  const systemName = AppConfig.systemInfo.name
  const formRef = ref<FormInstance>()
  const formData = reactive({
    username: '',
    password: '',
    rememberPassword: true
  })

  const rules = computed<FormRules>(() => ({
    username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
    password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
  }))

  const loading = ref(false)

  function loadRemembered() {
    try {
      const raw = localStorage.getItem(REMEMBER_KEY)
      if (!raw) return
      const saved = JSON.parse(raw) as { username?: string; password?: string }
      formData.username = saved.username || ''
      formData.password = saved.password || ''
      formData.rememberPassword = true
    } catch {
      /* ignore */
    }
  }

  function saveRemembered() {
    if (formData.rememberPassword) {
      localStorage.setItem(
        REMEMBER_KEY,
        JSON.stringify({ username: formData.username, password: formData.password })
      )
    } else {
      localStorage.removeItem(REMEMBER_KEY)
    }
  }

  async function checkInit() {
    try {
      const res = await fetchVerifySession()
      needsInit.value = res?.initialized === false
      if (!needsInit.value) ElMessage.success('系统已就绪，请登录')
    } catch {
      needsInit.value = false
    }
  }

  onMounted(() => {
    loadRemembered()
    checkInit()
  })

  const handleSubmit = async () => {
    if (!formRef.value) return

    try {
      const valid = await formRef.value.validate()
      if (!valid) return

      if (!isPassing.value) {
        isClickPass.value = true
        return
      }

      loading.value = true
      const { token, refreshToken } = await fetchLogin({
        userName: formData.username,
        password: formData.password
      })

      if (!token) throw new Error('Login failed - no token received')

      saveRemembered()
      userStore.setToken(token, refreshToken)
      userStore.setLoginStatus(true)
      showLoginSuccessNotice()

      const redirect = route.query.redirect as string
      router.push(redirect || '/')
    } catch (error) {
      if (error instanceof HttpError) {
        ElMessage.error(error.message || '登录失败')
      } else {
        console.error('[Login] Unexpected error:', error)
        ElMessage.error('登录失败')
      }
    } finally {
      loading.value = false
      resetDragVerify()
    }
  }

  const resetDragVerify = () => {
    dragVerify.value?.reset?.()
  }

  const showLoginSuccessNotice = () => {
    setTimeout(() => {
      ElNotification({
        title: t('login.success.title'),
        type: 'success',
        duration: 2500,
        zIndex: 10000,
        message: t('login.success.message') + ', ' + systemName + '!'
      })
    }, 300)
  }
</script>

<style scoped>
  @import './style.css';
</style>
