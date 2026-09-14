<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">风控日志</span>
          <ElSpace>
            <ElButton type="danger" plain @click="clear">清空</ElButton>
            <ElButton :loading="loading" @click="loadData">刷新</ElButton>
          </ElSpace>
        </div>
      </template>
      <ElTable :data="list" v-loading="loading" stripe border>
        <ElTableColumn prop="cookie_id" label="账号" width="120" />
        <ElTableColumn prop="risk_type" label="类型" width="140" />
        <ElTableColumn prop="message" label="描述" min-width="220" show-overflow-tooltip />
        <ElTableColumn prop="processing_status" label="状态" width="120" />
        <ElTableColumn prop="created_at" label="时间" width="180" />
      </ElTable>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { getRiskLogs, clearRiskLogs } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'AdminRiskLogs' })

  const loading = ref(false)
  const list = ref<any[]>([])

  async function loadData() {
    loading.value = true
    try {
      const res = await getRiskLogs({ page: 1, limit: 100 })
      list.value = res.data || []
    } finally {
      loading.value = false
    }
  }

  async function clear() {
    await ElMessageBox.confirm('确认清空风控日志？', '提示', { type: 'warning' })
    await clearRiskLogs()
    ElMessage.success('已清空')
    loadData()
  }

  onMounted(loadData)
</script>
