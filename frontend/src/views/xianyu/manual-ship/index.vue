<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span class="font-medium">手动补发</span>
          <ElSpace>
            <ElSelect
              v-model="filterCookieId"
              clearable
              filterable
              placeholder="全部账号"
              style="width: 200px"
              @change="loadData"
            >
              <ElOption
                v-for="a in accounts"
                :key="a.id"
                :label="a.nickname || a.remark || a.id"
                :value="a.id"
              >
                <div class="flex items-center gap-2">
                  <ElAvatar :size="20" :src="a.avatar_url" />
                  <span>{{ a.nickname || a.remark || a.id }}</span>
                </div>
              </ElOption>
            </ElSelect>
            <ElButton :loading="loading" @click="loadData">刷新待发货</ElButton>
          </ElSpace>
        </div>
      </template>

      <ElAlert
        class="mb-4"
        type="info"
        :closable="false"
        title="选择待发货订单后，可仅改状态或完整发货（匹配卡券发送）"
      />

      <ElTable :data="list" v-loading="loading" stripe border @selection-change="onSelect">
        <ElTableColumn type="selection" width="45" />
        <ElTableColumn prop="order_id" label="订单号" min-width="150" />
        <ElTableColumn label="账号" min-width="140">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <ElAvatar :size="22" :src="accountAvatar(row.cookie_id)" />
              <span>{{ accountName(row.cookie_id) }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="item_title" label="商品" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.item_title || row.item_id }}</template>
        </ElTableColumn>
        <ElTableColumn prop="item_id" label="商品ID" width="120" />
        <ElTableColumn prop="amount" label="金额" width="90" />
        <ElTableColumn prop="buyer_id" label="买家" width="110" show-overflow-tooltip />
        <ElTableColumn prop="status" label="状态" width="110" />
      </ElTable>

      <div class="mt-4">
        <ElRadioGroup v-model="shipMode">
          <ElRadio value="status_only">仅修改发货状态</ElRadio>
          <ElRadio value="full_delivery">完整发货</ElRadio>
        </ElRadioGroup>
        <ElInput
          v-if="shipMode === 'full_delivery'"
          v-model="content"
          class="mt-3"
          type="textarea"
          :rows="3"
          placeholder="可选自定义内容"
        />
        <ElButton
          class="mt-4"
          type="primary"
          :disabled="!selected.length"
          :loading="shipping"
          @click="doShip"
        >
          立即发货 ({{ selected.length }})
        </ElButton>
      </div>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import {
    getAccountDetails,
    getOrders,
    manualShipOrder,
    type AccountDetail,
    type Order,
    type ShipMode
  } from '@/api/xy'
  import { ElMessage } from 'element-plus'

  defineOptions({ name: 'ManualShip' })

  const loading = ref(false)
  const shipping = ref(false)
  const list = ref<Order[]>([])
  const accounts = ref<AccountDetail[]>([])
  const filterCookieId = ref('')
  const selected = ref<string[]>([])
  const shipMode = ref<ShipMode>('full_delivery')
  const content = ref('')

  const accountMap = computed(() => {
    const m: Record<string, AccountDetail> = {}
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
    return accountMap.value[id]?.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${id}`
  }

  async function loadData() {
    loading.value = true
    try {
      if (!accounts.value.length) accounts.value = await getAccountDetails()
      const res = await getOrders(filterCookieId.value || undefined, 'pending_ship', 1, 100)
      list.value = res.data || []
    } finally {
      loading.value = false
    }
  }

  function onSelect(rows: Order[]) {
    selected.value = rows.map((r) => r.order_id)
  }

  async function doShip() {
    shipping.value = true
    try {
      const res = await manualShipOrder(selected.value, shipMode.value, content.value || undefined)
      ElMessage.success(res.message || `成功 ${res.success_count}/${res.total}`)
      loadData()
    } finally {
      shipping.value = false
    }
  }

  onMounted(loadData)
</script>
