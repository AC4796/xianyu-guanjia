<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">数据日志 / 订单分析</span>
          <ElSpace>
            <ElSelect v-model="days" style="width: 120px" @change="loadData">
              <ElOption :value="7" label="近7天" />
              <ElOption :value="14" label="近14天" />
              <ElOption :value="30" label="近30天" />
            </ElSelect>
            <ElButton :loading="loading" @click="loadData">刷新</ElButton>
          </ElSpace>
        </div>
      </template>

      <ElRow :gutter="16" class="mb-4">
        <ElCol :span="8" v-for="c in cards" :key="c.label">
          <ElCard shadow="hover">
            <div class="text-sm text-gray-500">{{ c.label }}</div>
            <div class="mt-2 text-2xl font-bold">{{ c.value }}</div>
          </ElCard>
        </ElCol>
      </ElRow>

      <ElTable :data="rows" v-loading="loading" stripe border>
        <ElTableColumn prop="date" label="日期" width="140" />
        <ElTableColumn prop="count" label="订单数" width="120" />
        <ElTableColumn prop="amount" label="金额" width="120" />
        <ElTableColumn prop="status" label="状态分布" min-width="200" show-overflow-tooltip />
      </ElTable>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { getOrderAnalytics, getValidOrders } from '@/api/xy'

  defineOptions({ name: 'About' })

  const loading = ref(false)
  const days = ref(7)
  const analytics = ref<any>({})
  const validCount = ref(0)
  const rows = ref<any[]>([])

  const cards = computed(() => [
    { label: '分析区间(天)', value: days.value },
    { label: '有效订单', value: validCount.value },
    { label: '总订单', value: analytics.value.total || analytics.value.order_count || rows.value.length }
  ])

  async function loadData() {
    loading.value = true
    try {
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - days.value)
      const range = {
        start_date: start.toISOString().split('T')[0],
        end_date: end.toISOString().split('T')[0]
      }
      const [a, valid] = await Promise.all([
        getOrderAnalytics(range),
        getValidOrders(range).catch(() => [])
      ])
      analytics.value = a || {}
      validCount.value = valid.length
      rows.value =
        (a as any).daily ||
        (a as any).details ||
        (a as any).list ||
        Object.entries((a as any).by_date || {}).map(([date, v]: any) => ({
          date,
          count: v.count || v,
          amount: v.amount || '-',
          status: JSON.stringify(v.status || {})
        }))
    } finally {
      loading.value = false
    }
  }

  onMounted(loadData)
</script>
