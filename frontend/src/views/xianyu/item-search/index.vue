<template>
  <div class="art-full-height">
    <ElCard class="art-table-card" shadow="never">
      <ArtTableHeader v-model:columns="columnChecks" :loading="loading" @refresh="refreshSearch">
        <template #left>
          <ElSpace wrap>
            <ElInput
              v-model="keyword"
              placeholder="搜索闲鱼商品"
              style="width: 280px"
              clearable
              @keyup.enter="doSearch"
            />
            <ElButton type="primary" :loading="loading" @click="doSearch" v-ripple>搜索</ElButton>
          </ElSpace>
        </template>
      </ArtTableHeader>

      <ArtTable
        :loading="loading"
        :data="tableData"
        :columns="columns"
        :pagination="pagination"
        @selection-change="onSelect"
        @pagination:size-change="onSizeChange"
        @pagination:current-change="onPageChange"
      />
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { searchItems } from '@/api/xy'
  import { useTableColumns } from '@/hooks/core/useTableColumns'
  import { ElButton, ElImage, ElMessage, ElAvatar } from 'element-plus'

  defineOptions({ name: 'ItemSearch' })

  const loading = ref(false)
  const keyword = ref('')
  const tableData = ref<any[]>([])
  const selected = ref<any[]>([])
  const pagination = reactive({
    current: 1,
    size: 20,
    total: 0
  })

  function cover(row: any) {
    return row.main_image || row.pic_url || row.image || row.picUrl || row.pictUrl || ''
  }

  function wantText(row: any) {
    const w = row.want_num ?? row.want_count ?? row.wantNum
    return w === 0 || w ? w : '-'
  }

  function viewText(row: any) {
    const v = row.view_count ?? row.viewCount ?? row.browseCnt
    return v === 0 || v ? v : '-'
  }

  const { columnChecks, columns } = useTableColumns(() => [
    { type: 'selection', width: 48 },
    { type: 'index', width: 60, label: '序号' },
    {
      prop: 'cover',
      label: '封面',
      width: 80,
      formatter: (row: any) => {
        const src = cover(row)
        if (!src) return h('span', '-')
        return h(ElImage, {
          src,
          fit: 'cover',
          class: 'rounded',
          style: 'width:48px;height:48px',
          previewSrcList: [src],
          previewTeleported: true,
          hideOnClickModal: true,
          zIndex: 4000
        })
      }
    },
    { prop: 'item_id', label: '商品ID', minWidth: 140, showOverflowTooltip: true },
    {
      prop: 'title',
      label: '标题',
      minWidth: 220,
      showOverflowTooltip: true,
      formatter: (row: any) => row.title || row.item_title || '-'
    },
    {
      prop: 'price',
      label: '现价',
      width: 100,
      formatter: (row: any) => row.price || row.item_price || '-'
    },
    {
      prop: 'original_price',
      label: '原价/划线价',
      width: 110,
      formatter: (row: any) => row.original_price || row.oriPrice || '-'
    },
    {
      prop: 'seller',
      label: '卖家',
      minWidth: 160,
      formatter: (row: any) =>
        h('div', { class: 'flex items-center gap-2' }, [
          row.seller_avatar || row.avatar
            ? h(ElAvatar, { size: 24, src: row.seller_avatar || row.avatar })
            : null,
          h('span', row.seller_name || row.seller || row.nick || '-')
        ])
    },
    {
      prop: 'area',
      label: '地区',
      width: 100,
      showOverflowTooltip: true,
      formatter: (row: any) => row.area || row.city || row.location || '-'
    },
    {
      prop: 'want_view',
      label: '想要/浏览',
      width: 110,
      formatter: (row: any) => `${wantText(row)} / ${viewText(row)}`
    },
    {
      prop: 'publish_time',
      label: '发布时间',
      width: 140,
      formatter: (row: any) => row.publish_time || '-'
    },
    {
      prop: 'operation',
      label: '操作',
      width: 100,
      fixed: 'right',
      formatter: (row: any) =>
        h(
          ElButton,
          {
            link: true,
            type: 'primary',
            onClick: () => openItem(row)
          },
          () => '打开'
        )
    }
  ])

  function openItem(row: any) {
    const id = row.item_id || row.id
    if (!id) return
    window.open(row.item_url || `https://www.goofish.com/item?id=${id}`, '_blank')
  }

  function onSelect(rows: any[]) {
    selected.value = rows
  }

  async function fetchPage() {
    if (!keyword.value.trim()) {
      tableData.value = []
      pagination.total = 0
      return
    }
    loading.value = true
    try {
      const res: any = await searchItems({
        keyword: keyword.value,
        page: pagination.current,
        page_size: pagination.size
      })
      if (res?.error) ElMessage.error(res.error)
      const items = res?.data || res?.items || []
      tableData.value = items
      let total = Number(res?.total || items.length || 0)
      const hasMore = res?.has_more === true || items.length >= pagination.size
      if (hasMore) {
        total = Math.max(total, pagination.current * pagination.size + 1)
      } else {
        total = Math.max(total, (pagination.current - 1) * pagination.size + items.length)
      }
      pagination.total = total
      if (!items.length) ElMessage.info('未搜索到商品')
    } catch (e: any) {
      ElMessage.error(e?.message || '搜索失败')
    } finally {
      loading.value = false
    }
  }

  function doSearch() {
    if (!keyword.value.trim()) {
      ElMessage.warning('请输入关键词')
      return
    }
    pagination.current = 1
    fetchPage()
  }

  function refreshSearch() {
    if (keyword.value.trim()) fetchPage()
  }

  function onSizeChange(size: number) {
    pagination.size = size
    pagination.current = 1
    fetchPage()
  }

  function onPageChange(page: number) {
    pagination.current = page
    fetchPage()
  }
</script>
