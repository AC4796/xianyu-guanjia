<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header><span class="font-medium">免责声明</span></template>
      <div class="leading-7 text-gray-700 space-y-3">
        <p>本系统（闲鱼管家）仅供学习与研究使用，严禁用于任何商业牟利或违法违规用途。</p>
        <p>使用本系统即表示您已了解并同意：因使用本软件产生的一切后果由使用者自行承担。</p>
        <p>请遵守闲鱼平台规则及相关法律法规。开发者不对账号封禁、资金损失等承担任何责任。</p>
        <p>建议仅在自有账号、合法授权场景下使用自动化能力，并妥善保管 Cookie 与密钥。</p>
        <ElButton type="primary" @click="accept">我已阅读并同意</ElButton>
      </div>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { useUserStore } from '@/store/modules/user'
  import { ElMessage } from 'element-plus'

  defineOptions({ name: 'Disclaimer' })

  const userStore = useUserStore()

  function accept() {
    const uid = userStore.info.userId || 'guest'
    localStorage.setItem(`disclaimer_accepted_${uid}`, '1')
    ElMessage.success('已确认')
  }
</script>
