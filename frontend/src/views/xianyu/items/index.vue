<template>
  <div class="art-full-height">
    <ElCard class="art-table-card" shadow="never">
      <ArtTableHeader v-model:columns="columnChecks" :loading="loading" @refresh="loadData">
        <template #left>
          <ElSpace wrap>
            <ElSelect
              v-model="filterCookieId"
              placeholder="全部账号"
              style="width: 200px"
              clearable
              filterable
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
            <ElSelect v-model="syncAccount" placeholder="选择账号同步" style="width: 180px" clearable>
              <ElOption
                v-for="a in accounts"
                :key="a.id"
                :label="a.nickname || a.remark || a.id"
                :value="a.id"
              />
            </ElSelect>
            <ElButton type="primary" :disabled="!syncAccount" :loading="syncing" @click="sync" v-ripple>
              从账号同步
            </ElButton>
          </ElSpace>
        </template>
      </ArtTableHeader>

      <ArtTable
        :loading="loading"
        :data="pagedList"
        :columns="columns"
        :pagination="pagination"
        @selection-change="onSelect"
        @pagination:size-change="onSizeChange"
        @pagination:current-change="onPageChange"
      />
    </ElCard>

    <ElDialog v-model="editVisible" title="编辑商品（本地）" width="560px">
      <ElForm label-width="90px" v-if="editForm">
        <ElFormItem label="标题"><ElInput v-model="editForm.item_title" /></ElFormItem>
        <ElFormItem label="价格"><ElInput v-model="editForm.item_price" /></ElFormItem>
        <ElFormItem label="分类"><ElInput v-model="editForm.item_category" /></ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="editForm.item_description" type="textarea" :rows="3" />
        </ElFormItem>
        <ElFormItem label="详情JSON">
          <ElInput v-model="editForm.item_detail" type="textarea" :rows="6" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveEdit">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import {
    getItems,
    syncItemsFromAccount,
    deleteItem,
    updateItem,
    updateItemLocalStatus,
    updateItemMultiSpec,
    polishItem,
    getAccountDetails,
    type AccountDetail,
    type Item
  } from '@/api/xy'
  import { useTableColumns } from '@/hooks/core/useTableColumns'
  import { ElAvatar, ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElImage, ElMessage, ElMessageBox, ElSwitch, ElTag } from 'element-plus'

  defineOptions({ name: 'Items' })

  const loading = ref(false)
  const syncing = ref(false)
  const saving = ref(false)
  const actingId = ref('')
  const list = ref<Item[]>([])
  const accounts = ref<AccountDetail[]>([])
  const syncAccount = ref('')
  const filterCookieId = ref('')
  const selected = ref<Item[]>([])
  const pagination = reactive({ current: 1, size: 20, total: 0 })
  const editVisible = ref(false)
  const editForm = ref<Partial<Item> | null>(null)
  const editKey = ref<{ cookie_id: string; item_id: string } | null>(null)

  const accountMap = computed(() => {
    const m: Record<string, AccountDetail> = {}
    accounts.value.forEach((a) => {
      m[a.id] = a
    })
    return m
  })

  const pagedList = computed(() => {
    const start = (pagination.current - 1) * pagination.size
    return list.value.slice(start, start + pagination.size)
  })

  function accountName(id: string) {
    const a = accountMap.value[id]
    return a?.nickname || a?.remark || id
  }

  function accountAvatar(id: string) {
    return accountMap.value[id]?.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${id}`
  }

  function parsed(row: Item): Record<string, any> {
    if (row.item_detail_parsed && typeof row.item_detail_parsed === 'object') {
      return row.item_detail_parsed as Record<string, any>
    }
    if (row.item_detail) {
      try {
        return JSON.parse(row.item_detail)
      } catch {
        return {}
      }
    }
    return {}
  }

  function thumb(row: Item) {
    if (row.item_pic) return row.item_pic
    const p = parsed(row)
    return (
      p.picUrl ||
      p.pic_url ||
      (p.pic_info && (p.pic_info.picUrl || p.pic_info.url)) ||
      (p.detail_params && p.detail_params.picUrl) ||
      p.mainPic ||
      p.main_image ||
      p.image ||
      p.pictUrl ||
      (Array.isArray(p.imageInfos) && p.imageInfos[0]?.url) ||
      ''
    )
  }

  function wantCnt(row: Item) {
    if (row.want_num !== undefined && row.want_num !== null) return row.want_num
    const p = parsed(row)
    return p.want_num ?? p.wantNum ?? p.wantCnt ?? p.collectNum ?? '-'
  }

  function viewCnt(row: Item) {
    if (row.view_count !== undefined && row.view_count !== null) return row.view_count
    const p = parsed(row)
    return p.view_count ?? p.browseCnt ?? p.viewCnt ?? p.pv ?? '-'
  }

  const { columnChecks, columns } = useTableColumns(() => [
    { type: 'selection', width: 48 },
    { type: 'index', width: 60, label: '序号' },
    {
      prop: 'thumb',
      label: '缩略图',
      width: 80,
      formatter: (row: Item) => {
        const src = thumb(row)
        if (!src) return h('span', { class: 'text-g-400' }, '无图')
        return h(ElImage, {
          src,
          fit: 'cover',
          style: 'width:48px;height:48px;border-radius:6px',
          previewSrcList: [src],
          previewTeleported: true,
          hideOnClickModal: true,
          zIndex: 4000
        })
      }
    },
    { prop: 'item_id', label: '商品ID', minWidth: 130, showOverflowTooltip: true },
    {
      prop: 'account',
      label: '上家/账号',
      minWidth: 150,
      formatter: (row: Item) =>
        h('div', { class: 'flex items-center gap-2' }, [
          h(ElAvatar, { size: 22, src: row.account_avatar || accountAvatar(row.cookie_id) }),
          h('div', { class: 'min-w-0' }, [
            h(
              'div',
              { class: 'truncate' },
              row.seller_name || row.account_nickname || accountName(row.cookie_id)
            ),
            h('div', { class: 'text-xs text-g-400 truncate' }, row.cookie_id)
          ])
        ])
    },
    {
      prop: 'title',
      label: '标题',
      minWidth: 200,
      showOverflowTooltip: true,
      formatter: (row: Item) =>
        h(
          'a',
          {
            class: 'text-primary hover:underline',
            href: `https://www.goofish.com/item?id=${row.item_id}`,
            target: '_blank',
            rel: 'noopener'
          },
          row.item_title || row.title || '-'
        )
    },
    {
      prop: 'price',
      label: '现价',
      width: 100,
      formatter: (row: Item) => row.item_price || row.price || '-'
    },
    {
      prop: 'original_price',
      label: '原价',
      width: 100,
      formatter: (row: Item) => row.original_price || parsed(row).original_price || '-'
    },
    {
      prop: 'category',
      label: '分类',
      width: 110,
      showOverflowTooltip: true,
      formatter: (row: Item) => row.item_category || parsed(row).category || '-'
    },
    {
      prop: 'want_view',
      label: '想要/浏览',
      width: 110,
      formatter: (row: Item) => `${wantCnt(row)} / ${viewCnt(row)}`
    },
    {
      prop: 'status',
      label: '状态',
      width: 90,
      formatter: (row: Item) =>
        h(
          ElTag,
          { type: row.local_status === 'off' ? 'info' : 'success', size: 'small' },
          () => (row.local_status === 'off' ? '已下架' : '在售')
        )
    },
    {
      prop: 'multi',
      label: '多规格',
      width: 90,
      formatter: (row: Item) =>
        h(ElSwitch, {
          modelValue: !!row.is_multi_spec,
          'onUpdate:modelValue': (v: string | number | boolean) => toggleMultiSpec(row, !!v)
        })
    },
    {
      prop: 'operation',
      label: '操作',
      width: 200,
      fixed: 'right',
      formatter: (row: Item) =>
        h('div', { class: 'flex items-center gap-1' }, [
          h(
            ElButton,
            {
              link: true,
              type: row.local_status === 'off' ? 'success' : 'warning',
              loading: actingId.value === row.item_id,
              onClick: () => setStatus(row, row.local_status === 'off' ? 'on' : 'off')
            },
            () => (row.local_status === 'off' ? '上架' : '下架')
          ),
          h(
            ElDropdown,
            {
              trigger: 'click',
              onCommand: (cmd: string) => onAction(cmd, row)
            },
            {
              default: () => h(ElButton, { link: true, type: 'primary' }, () => '更多'),
              dropdown: () =>
                h(ElDropdownMenu, null, () => [
                  h(ElDropdownItem, { command: 'edit' }, () => '编辑本地'),
                  h(ElDropdownItem, { command: 'polish' }, () => '擦亮'),
                  h(ElDropdownItem, { command: 'xianyu' }, () => '打开闲鱼'),
                  h(ElDropdownItem, { command: 'delete', divided: true }, () => '删除本地')
                ])
            }
          )
        ])
    }
  ])

  async function loadData() {
    loading.value = true
    try {
      ;[list.value, accounts.value] = await Promise.all([
        getItems(filterCookieId.value || undefined),
        getAccountDetails()
      ])
      pagination.total = list.value.length
      const maxPage = Math.max(1, Math.ceil(pagination.total / pagination.size) || 1)
      if (pagination.current > maxPage) pagination.current = maxPage
    } finally {
      loading.value = false
    }
  }

  function onSelect(rows: Item[]) {
    selected.value = rows
  }

  function onSizeChange(size: number) {
    pagination.size = size
    pagination.current = 1
  }

  function onPageChange(page: number) {
    pagination.current = page
  }

  async function sync() {
    if (!syncAccount.value) return
    syncing.value = true
    try {
      await syncItemsFromAccount(syncAccount.value)
      ElMessage.success('同步完成（含想要/浏览/原价标签）')
      filterCookieId.value = syncAccount.value
      await loadData()
    } finally {
      syncing.value = false
    }
  }

  async function remove(row: Item) {
    await ElMessageBox.confirm('确认删除该商品（仅本地）？', '提示', { type: 'warning' })
    await deleteItem(row.cookie_id, row.item_id)
    ElMessage.success('已删除')
    loadData()
  }

  async function setStatus(row: Item, status: 'on' | 'off') {
    actingId.value = row.item_id
    try {
      const res: any = await updateItemLocalStatus(row.cookie_id, row.item_id, status)
      const ok = res?.success !== false
      const msg = res?.message || (status === 'on' ? '上架完成' : '下架完成')
      if (ok) ElMessage.success(msg)
      else ElMessage.warning(msg)
      loadData()
    } finally {
      actingId.value = ''
    }
  }

  async function doPolish(row: Item) {
    actingId.value = row.item_id
    try {
      const res: any = await polishItem(row.cookie_id, row.item_id)
      if (res?.success) ElMessage.success(res.message || '擦亮成功')
      else ElMessage.warning(res?.message || '擦亮失败')
    } finally {
      actingId.value = ''
    }
  }

  function onAction(cmd: string, row: Item) {
    if (cmd === 'edit') openEdit(row)
    else if (cmd === 'polish') doPolish(row)
    else if (cmd === 'xianyu') window.open(`https://www.goofish.com/item?id=${row.item_id}`, '_blank')
    else if (cmd === 'delete') remove(row)
  }

  async function toggleMultiSpec(row: Item, enabled: boolean) {
    await updateItemMultiSpec(row.cookie_id, row.item_id, enabled)
    ElMessage.success('已更新')
    loadData()
  }

  function openEdit(row: Item) {
    editKey.value = { cookie_id: row.cookie_id, item_id: row.item_id }
    editForm.value = {
      item_title: row.item_title || row.title || '',
      item_price: String(row.item_price || row.price || ''),
      item_category: row.item_category || '',
      item_description: row.item_description || row.desc || '',
      item_detail: row.item_detail || JSON.stringify(row.item_detail_parsed || {}, null, 2)
    }
    editVisible.value = true
  }

  async function saveEdit() {
    if (!editKey.value || !editForm.value) return
    saving.value = true
    try {
      let detailObj: Record<string, any> = {}
      try {
        detailObj = JSON.parse(editForm.value.item_detail || '{}')
      } catch {
        ElMessage.error('详情 JSON 格式错误')
        return
      }
      detailObj.title = editForm.value.item_title
      detailObj.price = editForm.value.item_price
      detailObj.category = editForm.value.item_category
      detailObj.desc = editForm.value.item_description
      await updateItem(editKey.value.cookie_id, editKey.value.item_id, {
        item_detail: JSON.stringify(detailObj)
      } as any)
      ElMessage.success('已保存')
      editVisible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  onMounted(loadData)
</script>
