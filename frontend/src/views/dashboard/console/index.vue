<template>
  <div class="art-full-height p-4">
    <ElRow :gutter="20" class="flex">
      <ElCol v-for="(item, index) in dataList" :key="index" :xs="12" :sm="12" :md="6" :lg="6">
        <div class="art-card relative flex flex-col justify-center h-35 px-5 mb-5 max-sm:mb-4">
          <span class="text-g-700 text-sm">{{ item.des }}</span>
          <ArtCountTo class="text-[26px] font-medium mt-2" :target="item.num" :duration="1300" />
          <div class="flex-c mt-1">
            <span class="text-xs text-g-600">{{ item.sub }}</span>
          </div>
          <div
            class="absolute top-0 bottom-0 right-5 m-auto size-12.5 rounded-xl flex-cc bg-theme/10"
          >
            <ArtSvgIcon :icon="item.icon" class="text-xl text-theme" />
          </div>
        </div>
      </ElCol>
    </ElRow>

    <div class="art-card p-5">
      <div class="flex items-center justify-between mb-4">
        <span class="font-medium text-g-900">快捷入口</span>
        <ElButton text type="primary" :loading="loading" @click="loadStats">刷新</ElButton>
      </div>
      <ElSpace wrap>
        <ElButton v-for="item in shortcuts" :key="item.path" @click="$router.push(item.path)">
          {{ item.label }}
        </ElButton>
      </ElSpace>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { getAdminStats, getAccountDetails, getOrders } from '@/api/xy'

  defineOptions({ name: 'Console' })

  const loading = ref(false)
  const stats = reactive({
    accounts: 0,
    enabledAccounts: 0,
    orders: 0,
    pending: 0
  })

  const dataList = computed(() => [
    {
      des: '账号总数',
      icon: 'ri:user-3-line',
      num: stats.accounts,
      sub: '已绑定闲鱼账号'
    },
    {
      des: '启用账号',
      icon: 'ri:shield-check-line',
      num: stats.enabledAccounts,
      sub: '监听 / 自动回复中'
    },
    {
      des: '订单总数',
      icon: 'ri:shopping-bag-3-line',
      num: stats.orders,
      sub: '系统记录订单'
    },
    {
      des: '待发货',
      icon: 'ri:truck-line',
      num: stats.pending,
      sub: '需处理发货'
    }
  ])

  const shortcuts = [
    { label: '闲鱼账号', path: '/accounts' },
    { label: '订单管理', path: '/trade/orders' },
    { label: '关键词回复', path: '/auto-reply/keywords' },
    { label: '卡券管理', path: '/delivery/cards' },
    { label: '发货规则', path: '/delivery/rules' },
    { label: '系统设置', path: '/system-xy/settings' }
  ]

  async function loadStats() {
    loading.value = true
    try {
      const [accounts, ordersRes, admin] = await Promise.all([
        getAccountDetails().catch(() => []),
        getOrders(undefined, undefined, 1, 1).catch(() => ({ total: 0, data: [] })),
        getAdminStats().catch(() => ({} as any))
      ])
      stats.accounts = accounts.length
      stats.enabledAccounts = accounts.filter((a) => a.enabled).length
      stats.orders = (admin as any).total_orders || ordersRes.total || 0
      stats.pending = (admin as any).pending_orders || 0
    } finally {
      loading.value = false
    }
  }

  onMounted(loadStats)
</script>
