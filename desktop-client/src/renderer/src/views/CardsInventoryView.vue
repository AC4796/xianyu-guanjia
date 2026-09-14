<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NImage,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns,
  type SelectRenderLabel,
  type SelectRenderTag
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import { getItems, type ItemRow } from '../api/items'
import {
  createCard,
  deleteCard,
  getCards,
  updateCard,
  type CardRow
} from '../api/delivery'

const message = useMessage()
const dialog = useDialog()
const accountStore = useAccountStore()
const loading = ref(false)
const saving = ref(false)
const cards = ref<CardRow[]>([])
const showModal = ref(false)
const editingId = ref<number | string | null>(null)
const localItems = ref<ItemRow[]>([])
const selectedItemIds = ref<string[]>([])

const form = ref({
  name: '',
  type: 'data',
  description: '',
  text_content: '',
  data_content: '',
  image_url: '',
  api_config: '',
  enabled: true,
  delay_seconds: 0
})

const typeOptions = [
  { label: '卡密库存（一行一条，发完自动扣除）', value: 'data' },
  { label: '固定文本', value: 'text' },
  { label: '图片', value: 'image' },
  { label: 'API 动态获取', value: 'api' }
]

const itemOptions = computed(() =>
  localItems.value.map((it) => {
    const id = String(it.item_id || it.id || '')
    const title = String((it as any).item_title || it.title || id)
    const pic = String(
      (it as any).item_pic || (it as any).main_image || it.pic_url || (it as any).pic || ''
    )
    return {
      label: `${title.slice(0, 36)}（${id}）`,
      value: id,
      title,
      pic
    }
  })
)

const renderItemLabel: SelectRenderLabel = (option) => {
  const pic = String((option as any).pic || '')
  const title = String((option as any).title || option.label || '')
  const id = String(option.value || '')
  return h(
    'div',
    { style: 'display:flex;align-items:center;gap:8px;padding:2px 0' },
    [
      pic
        ? h(NImage, {
            src: pic,
            width: 36,
            height: 36,
            objectFit: 'cover',
            style: 'border-radius:4px;flex-shrink:0',
            previewDisabled: true
          })
        : h('div', {
            style: 'width:36px;height:36px;border-radius:4px;background:#eee;flex-shrink:0'
          }),
      h('div', { style: 'min-width:0' }, [
        h(
          'div',
          {
            style:
              'font-size:13px;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:320px'
          },
          title
        ),
        h('div', { style: 'font-size:11px;opacity:0.6' }, id)
      ])
    ]
  )
}

const renderItemTag: SelectRenderTag = ({ option, handleClose }) => {
  const pic = String((option as any)?.pic || '')
  const title = String((option as any)?.title || option?.label || option?.value || '')
  return h(
    NTag,
    {
      size: 'small',
      closable: true,
      onClose: (e: MouseEvent) => {
        e.stopPropagation()
        handleClose()
      },
      style: 'padding: 0 6px 0 2px; display: inline-flex; align-items: center; gap: 4px'
    },
    {
      default: () =>
        h('span', { style: 'display:inline-flex;align-items:center;gap:4px;max-width:160px' }, [
          pic
            ? h(NImage, {
                src: pic,
                width: 20,
                height: 20,
                objectFit: 'cover',
                style: 'border-radius:3px;flex-shrink:0',
                previewDisabled: true
              })
            : null,
          h(
            'span',
            {
              style:
                'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px'
            },
            title.slice(0, 20)
          )
        ])
    }
  )
}

function stockCount(r: CardRow): number {
  if (r.type !== 'data') return -1
  const raw = String(r.data_content || r.data || '')
  return raw
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean).length
}

function contentPreview(r: CardRow): string {
  if (r.type === 'data') {
    const n = stockCount(r)
    return `剩余 ${n} 条卡密`
  }
  if (r.type === 'text') return String(r.text_content || r.content || '').slice(0, 80)
  if (r.type === 'image') return String(r.image_url || '')
  if (r.type === 'api') return String(r.api_config || '').slice(0, 80)
  return ''
}

function boundNames(r: CardRow): string[] {
  const names = (r.bound_names as string[]) || []
  if (names.length) return names.map(String)
  const items = (r.bound_items as Array<{ title?: string; item_id?: string }>) || []
  if (items.length) return items.map((b) => String(b.title || b.item_id || ''))
  const ids = (r.item_ids as string[]) || []
  return ids.map(String)
}

function boundItemsRich(r: CardRow): Array<{
  item_id?: string
  title?: string
  item_pic?: string
  offline?: boolean
}> {
  return ((r.bound_items as any[]) || []).map((b) => ({
    item_id: b?.item_id,
    title: b?.title || b?.item_id,
    item_pic: b?.item_pic || b?.main_image || '',
    offline: !!b?.offline
  }))
}

const columns: DataTableColumns<CardRow> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '名称', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'type',
    width: 100,
    render: (r) =>
      ({ data: '卡密', text: '文本', image: '图片', api: 'API' } as Record<string, string>)[
        String(r.type)
      ] || String(r.type)
  },
  {
    title: '绑定商品',
    key: 'bound',
    ellipsis: { tooltip: true },
    render: (r) => {
      const rich = boundItemsRich(r)
      if (!rich.length) {
        const names = boundNames(r)
        if (!names.length) return h(NText, { depth: 3 }, () => '未绑定')
        return h(NSpace, { size: 4, wrap: true }, () =>
          names.slice(0, 4).map((n) =>
            h(NTag, { size: 'small', type: 'info' }, () => (n.length > 18 ? `${n.slice(0, 18)}…` : n))
          )
        )
      }
      return h(NSpace, { size: 8, wrap: true }, () =>
        rich.slice(0, 4).map((b) =>
          h(
            'div',
            {
              style:
                'display:flex;align-items:center;gap:6px;max-width:200px;padding:2px 6px;border:1px solid #eee;border-radius:6px'
            },
            [
              b.item_pic
                ? h(NImage, {
                    src: b.item_pic,
                    width: 28,
                    height: 28,
                    objectFit: 'cover',
                    style: 'border-radius:4px;flex-shrink:0'
                  })
                : null,
              h(
                'span',
                {
                  style: `font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;${
                    b.offline ? 'color:#d03050' : ''
                  }`
                },
                String(b.title || b.item_id || '').slice(0, 24)
              )
            ]
          )
        ).concat(
          rich.length > 4 ? [h(NTag, { size: 'small' }, () => `+${rich.length - 4}`)] : []
        )
      )
    }
  },
  {
    title: '库存/内容',
    key: 'stock',
    ellipsis: { tooltip: true },
    render: (r) => {
      if (r.type === 'data') {
        const n = stockCount(r)
        return h(NTag, { size: 'small', type: n > 0 ? 'success' : 'warning' }, () => `剩余 ${n}`)
      }
      return contentPreview(r) || '-'
    }
  },
  {
    title: '启用',
    key: 'enabled',
    width: 70,
    render: (r) => (r.enabled === false ? '关' : '开')
  },
  {
    title: '操作',
    key: 'op',
    width: 160,
    render: (r) =>
      h(NSpace, { size: 6 }, () => [
        h(NButton, { size: 'tiny', onClick: () => openEdit(r) }, () => '编辑'),
        h(
          NButton,
          {
            size: 'tiny',
            type: 'error',
            secondary: true,
            onClick: () => {
              dialog.warning({
                title: '删除卡密库存',
                content: `确认删除「${r.name}」？关联的发货规则也会受影响。`,
                positiveText: '删除',
                negativeText: '取消',
                onPositiveClick: async () => {
                  await deleteCard(r.id!)
                  message.success('已删除')
                  await load()
                }
              })
            }
          },
          () => '删除'
        )
      ])
  }
]

function openCreate(): void {
  editingId.value = null
  selectedItemIds.value = []
  form.value = {
    name: '',
    type: 'data',
    description: '',
    text_content: '',
    data_content: '',
    image_url: '',
    api_config: '',
    enabled: true,
    delay_seconds: 0
  }
  showModal.value = true
  void loadLocalItems()
}

function openEdit(r: CardRow): void {
  editingId.value = r.id ?? null
  const ids = ((r.item_ids as string[]) || []).map(String)
  if (!ids.length) {
    const bounds = (r.bound_items as Array<{ item_id?: string }>) || []
    selectedItemIds.value = bounds.map((b) => String(b.item_id || '')).filter(Boolean)
  } else {
    selectedItemIds.value = ids
  }
  form.value = {
    name: String(r.name || ''),
    type: String(r.type || 'data'),
    description: String(r.description || ''),
    text_content: String(r.text_content || r.content || ''),
    data_content: String(r.data_content || r.data || ''),
    image_url: String(r.image_url || ''),
    api_config:
      typeof r.api_config === 'string'
        ? r.api_config
        : r.api_config
          ? JSON.stringify(r.api_config, null, 2)
          : '',
    enabled: r.enabled !== false,
    delay_seconds: Number(r.delay_seconds || 0)
  }
  showModal.value = true
  void loadLocalItems()
}

async function loadLocalItems(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    localItems.value = []
    return
  }
  try {
    localItems.value = await getItems(cid)
  } catch {
    localItems.value = []
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    cards.value = await getCards()
  } catch (e: any) {
    message.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  if (!form.value.name.trim()) {
    message.warning('请填写名称')
    return
  }
  if (form.value.type === 'data' && !form.value.data_content.trim()) {
    message.warning('请粘贴卡密，一行一条')
    return
  }
  if (form.value.type === 'text' && !form.value.text_content.trim()) {
    message.warning('请填写文本内容')
    return
  }
  if (!selectedItemIds.value.length) {
    message.warning('请至少关联一个本地商品，否则自动发货不知道发哪份库存')
    return
  }
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      name: form.value.name.trim(),
      type: form.value.type,
      description: form.value.description,
      text_content: form.value.text_content,
      data_content: form.value.data_content,
      image_url: form.value.image_url,
      enabled: form.value.enabled,
      delay_seconds: form.value.delay_seconds,
      item_ids: selectedItemIds.value
    }
    if (form.value.type === 'api') {
      try {
        payload.api_config = form.value.api_config.trim()
          ? JSON.parse(form.value.api_config)
          : {}
      } catch {
        message.warning('API 配置需为合法 JSON')
        saving.value = false
        return
      }
    }
    if (editingId.value != null) {
      await updateCard(editingId.value, payload)
      message.success(`已更新，当前绑定 ${selectedItemIds.value.length} 个商品`)
    } else {
      const res: any = await createCard(payload)
      const n = Array.isArray(res?.bound_items)
        ? res.bound_items.length
        : selectedItemIds.value.length
      message.success(`已创建，并关联 ${n} 个商品（付款后按商品 ID 自动发卡密）`)
    }
    showModal.value = false
    await load()
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const dataHint = computed(() => {
  if (form.value.type !== 'data') return ''
  const n = form.value.data_content
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean).length
  return `当前共 ${n} 条；买家付款自动发货时会按行扣除，发完即空`
})

watch(
  () => accountStore.activeCookieId,
  () => void loadLocalItems()
)

onMounted(() => {
  void load()
  void loadLocalItems()
})
</script>

<template>
  <n-space vertical :size="14">
    <n-card title="卡密库存" size="small">
      <AccountTabs />
      <n-text depth="3" style="display: block; margin: 8px 0 12px; font-size: 12px">
        列表会显示已绑定商品名。新建/编辑时可多选增减商品：买家买哪个商品，就发对应这份卡密。
      </n-text>
      <n-space style="margin-bottom: 12px">
        <n-button type="primary" @click="openCreate">新建库存</n-button>
        <n-button secondary :loading="loading" @click="load">刷新</n-button>
      </n-space>
      <n-data-table :loading="loading" :columns="columns" :data="cards" size="small" />
    </n-card>

    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="editingId != null ? '编辑卡密库存' : '新建卡密库存'"
      style="width: 720px"
    >
      <n-form label-placement="left" label-width="100">
        <n-form-item label="名称">
          <n-input v-model:value="form.name" placeholder="如：月卡卡密 / 自动回复文案" />
        </n-form-item>
        <n-form-item label="类型">
          <n-select v-model:value="form.type" :options="typeOptions" />
        </n-form-item>
        <n-form-item label="关联商品" required>
          <n-space vertical style="width: 100%">
            <n-select
              v-model:value="selectedItemIds"
              multiple
              filterable
              :options="itemOptions"
              :render-label="renderItemLabel"
              :render-tag="renderItemTag"
              placeholder="多选本地商品；保存后立即增删绑定"
            />
            <n-text depth="3" style="font-size: 12px">
              先在「商品管理」同步本账号商品。已选 {{ selectedItemIds.length }} 个；保存即生效。
            </n-text>
          </n-space>
        </n-form-item>
        <n-form-item label="说明">
          <n-input v-model:value="form.description" placeholder="可选" />
        </n-form-item>
        <n-form-item v-if="form.type === 'text'" label="文本内容">
          <n-input v-model:value="form.text_content" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" />
        </n-form-item>
        <n-form-item v-if="form.type === 'data'" label="卡密列表">
          <n-space vertical style="width: 100%">
            <n-input
              v-model:value="form.data_content"
              type="textarea"
              :autosize="{ minRows: 8, maxRows: 16 }"
              placeholder="一行一条卡密，例如：&#10;ABCD-1111&#10;ABCD-2222"
            />
            <n-text depth="3" style="font-size: 12px">{{ dataHint }}</n-text>
          </n-space>
        </n-form-item>
        <n-form-item v-if="form.type === 'image'" label="图片 URL">
          <n-input v-model:value="form.image_url" />
        </n-form-item>
        <n-form-item v-if="form.type === 'api'" label="API 配置">
          <n-input v-model:value="form.api_config" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
      </n-form>
      <n-space justify="end">
        <n-button @click="showModal = false">取消</n-button>
        <n-button type="primary" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>
