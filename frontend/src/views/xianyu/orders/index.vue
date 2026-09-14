<template>
  <div class="art-full-height">
    <ElCard class="art-table-card" shadow="never">
      <ArtTableHeader v-model:columns="columnChecks" :loading="loading" @refresh="loadData">
        <template #left>
          <ElSpace wrap>
            <ElSelect
              v-model="filterCookieId"
              clearable
              filterable
              placeholder="全部账号"
              style="width: 200px"
              @change="onFilterChange"
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
            <ElSelect v-model="filterStatus" clearable placeholder="状态" style="width: 140px">
              <ElOption label="全部" value="all" />
              <ElOption label="待发货" value="pending_ship" />
              <ElOption label="已发货" value="shipped" />
              <ElOption label="已完成" value="completed" />
              <ElOption label="已取消" value="cancelled" />
            </ElSelect>
            <ElButton type="primary" :loading="syncing" @click="syncAll" v-ripple>一键同步</ElButton>
            <ElButton
              type="warning"
              :disabled="!selected.length"
              @click="openShip(selected)"
              v-ripple
              >批量发货</ElButton
            >
          </ElSpace>
        </template>
      </ArtTableHeader>

      <ElAlert class="mb-3" type="info" :closable="false" show-icon>
        同步会优先用在线账号登录态拉取「我卖出的」。闲鱼未公开卖家订单列表接口时，可能拉空；新成交仍会从聊天自动入库。
      </ElAlert>

      <ArtTable
        :loading="loading"
        :data="list"
        :columns="columns"
        :pagination="pagination"
        @selection-change="onSelect"
        @pagination:size-change="onSizeChange"
        @pagination:current-change="onPageChange"
      />
    </ElCard>

    <ElDrawer v-model="detailVisible" title="订单详情" size="420px">
      <pre class="text-xs whitespace-pre-wrap">{{ detailJson }}</pre>
    </ElDrawer>

    <ElDialog v-model="shipVisible" title="手动发货" width="480px">
      <ElRadioGroup v-model="shipMode" class="flex flex-col items-start gap-3">
        <ElRadio value="status_only">仅修改闲鱼发货状态</ElRadio>
        <ElRadio value="full_delivery">完整发货（匹配卡券并发送）</ElRadio>
      </ElRadioGroup>
      <ElInput
        v-if="shipMode === 'full_delivery'"
        v-model="shipContent"
        class="mt-4"
        type="textarea"
        :rows="3"
        placeholder="可选：自定义发货内容"
      />
      <template #footer>
        <ElButton @click="shipVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="shipping" @click="doShip">确认发货</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import {
    getAccountDetails,
    getOrders,
    getOrderDetail,
    deleteOrder,
    syncOrders,
    syncSingleOrder,
    manualShipOrder,
    type AccountDetail,
    type Order,
    type ShipMode
  } from '@/api/xy'
  import { useTableColumns } from '@/hooks/core/useTableColumns'
  import { ElAvatar, ElButton, ElMessage, ElMessageBox, ElTag } from 'element-plus'

  defineOptions({ name: 'Orders' })

  const loading = ref(false)
  const syncing = ref(false)
  const shipping = ref(false)
  const list = ref<(Order & { _syncing?: boolean })[]>([])
  const accounts = ref<AccountDetail[]>([])
  const filterStatus = ref('all')
  const filterCookieId = ref('')
  const selected = ref<string[]>([])
  const pagination = reactive({ current: 1, size: 20, total: 0 })

  const detailVisible = ref(false)
  const detailJson = ref('')
  const shipVisible = ref(false)
  const shipIds = ref<string[]>([])
  const shipMode = ref<ShipMode>('full_delivery')
  const shipContent = ref('')

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

  const statusType: Record<string, any> = {
    pending_ship: 'warning',
    shipped: 'primary',
    completed: 'success',
    cancelled: 'info',
    refunding: 'danger'
  }

  const { columnChecks, columns } = useTableColumns(() => [
    { type: 'selection', width: 48 },
    { type: 'index', width: 60, label: '序号' },
    { prop: 'order_id', label: '订单号', minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'account',
      label: '账号',
      minWidth: 140,
      formatter: (row: Order) =>
        h('div', { class: 'flex items-center gap-2' }, [
          h(ElAvatar, { size: 22, src: accountAvatar(row.cookie_id) }),
          h('span', accountName(row.cookie_id))
        ])
    },
    {
      prop: 'item_title',
      label: '商品',
      minWidth: 160,
      showOverflowTooltip: true,
      formatter: (row: Order) => row.item_title || row.item_id || '-'
    },
    { prop: 'item_id', label: '商品ID', width: 120, showOverflowTooltip: true },
    { prop: 'amount', label: '金额', width: 90 },
    {
      prop: 'status',
      label: '状态',
      width: 110,
      formatter: (row: Order) =>
        h(ElTag, { size: 'small', type: statusType[row.status || ''] || 'info' }, () => row.status || '-')
    },
    { prop: 'buyer_id', label: '买家', width: 110, showOverflowTooltip: true },
    { prop: 'receiver_name', label: '收货人', width: 100 },
    {
      prop: 'operation',
      label: '操作',
      width: 260,
      fixed: 'right',
      formatter: (row: Order & { _syncing?: boolean }) =>
        h('div', { class: 'flex flex-wrap gap-1' }, [
          h(ElButton, { link: true, type: 'primary', onClick: () => showDetail(row.order_id) }, () => '详情'),
          h(
            ElButton,
            { link: true, loading: !!row._syncing, onClick: () => syncOne(row) },
            () => '同步'
          ),
          h(ElButton, { link: true, type: 'warning', onClick: () => openShip([row.order_id]) }, () => '发货'),
          h(ElButton, { link: true, type: 'danger', onClick: () => remove(row.order_id) }, () => '删除')
        ])
    }
  ])

  watch(filterStatus, () => {
    pagination.current = 1
    loadData()
  })

  function onFilterChange() {
    pagination.current = 1
    loadData()
  }

  async function loadData() {
    loading.value = true
    try {
      if (!accounts.value.length) accounts.value = await getAccountDetails()
      const res = await getOrders(
        filterCookieId.value || undefined,
        filterStatus.value,
        pagination.current,
        pagination.size
      )
      list.value = res.data || []
      pagination.total = res.total || 0
    } finally {
      loading.value = false
    }
  }

  function onSelect(rows: Order[]) {
    selected.value = rows.map((r) => r.order_id)
  }

  function onSizeChange(size: number) {
    pagination.size = size
    pagination.current = 1
    loadData()
  }

  function onPageChange(page: number) {
    pagination.current = page
    loadData()
  }

  async function syncAll() {
    syncing.value = true
    try {
      const res = await syncOrders(
        filterCookieId.value || undefined,
        filterStatus.value === 'all' ? undefined : filterStatus.value
      )
      const pull = (res as any)?.pull
      const summary = (res as any)?.summary
      const parts: string[] = []
      if (pull?.fetched != null) parts.push(`拉取 ${pull.fetched} 条`)
      if (pull?.saved != null) parts.push(`入库 ${pull.saved} 条`)
      if (summary) {
        parts.push(
          `刷新：更新 ${summary.updated || 0} / 无变化 ${summary.no_change || 0} / 失败 ${summary.failed || 0}`
        )
      }
      const msg = parts.length ? parts.join('；') : (res as any)?.message || '同步完成'
      if ((pull?.fetched || 0) === 0 && (summary?.total || 0) === 0) {
        ElMessage.warning((res as any)?.message || msg)
      } else {
        ElMessage.success(msg)
      }
      await loadData()
    } catch (e: any) {
      ElMessage.error(e?.message || '同步失败')
    } finally {
      syncing.value = false
    }
  }

  async function syncOne(row: Order & { _syncing?: boolean }) {
    row._syncing = true
    try {
      await syncSingleOrder(row.order_id)
      ElMessage.success('已同步')
      loadData()
    } catch (e: any) {
      ElMessage.error(e?.message || '同步失败')
    } finally {
      row._syncing = false
    }
  }

  async function showDetail(orderId: string) {
    const res = await getOrderDetail(orderId)
    detailJson.value = JSON.stringify(res.data || {}, null, 2)
    detailVisible.value = true
  }

  function openShip(ids: string[]) {
    shipIds.value = ids
    shipMode.value = 'full_delivery'
    shipContent.value = ''
    shipVisible.value = true
  }

  async function doShip() {
    shipping.value = true
    try {
      const res = await manualShipOrder(shipIds.value, shipMode.value, shipContent.value || undefined)
      ElMessage.success((res as any)?.message || '已提交发货')
      shipVisible.value = false
      loadData()
    } catch (e: any) {
      ElMessage.error(e?.message || '发货失败')
    } finally {
      shipping.value = false
    }
  }

  async function remove(orderId: string) {
    await ElMessageBox.confirm('确认删除该订单？', '提示', { type: 'warning' })
    await deleteOrder(orderId)
    ElMessage.success('已删除')
    loadData()
  }

  onMounted(loadData)
</script>
