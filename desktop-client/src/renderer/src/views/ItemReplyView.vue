<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
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
  useDialog,
  useMessage,
  type DataTableColumns,
  type FormInst,
  type FormRules,
  type SelectOption
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  addItemReply,
  deleteItemReply,
  getItemReplies,
  updateItemReply,
  type ItemReplyRow
} from '../api/itemReplies'
import { getItems, type ItemRow } from '../api/items'

const message = useMessage()
const dialog = useDialog()
const accountStore = useAccountStore()
const loading = ref(false)
const rows = ref<ItemReplyRow[]>([])
const showModal = ref(false)
const editing = ref<ItemReplyRow | null>(null)
const formRef = ref<FormInst | null>(null)
const itemOptions = ref<SelectOption[]>([])
const itemMap = ref<Record<string, ItemRow>>({})
const form = ref({ item_ids: [] as string[], reply: '', title: '' })

const rules: FormRules = {
  reply: { required: true, message: '请输入回复内容', trigger: 'blur' }
}

function rowId(r: ItemReplyRow): string {
  return String(r.id || `${r.cookie_id || ''}::${r.item_id || ''}`)
}

const columns: DataTableColumns<ItemReplyRow> = [
  {
    title: '商品',
    key: 'item',
    width: 220,
    render: (r) => {
      const id = String(r.item_id || '')
      const it = itemMap.value[id]
      const pic = String(it?.item_pic || it?.pic_url || r.item_pic || '')
      const title = String(r.title || r.item_title || it?.title || it?.item_title || id)
      return h('div', { style: 'display:flex;align-items:center;gap:8px' }, [
        pic
          ? h(NImage, {
              src: pic,
              width: 40,
              height: 40,
              objectFit: 'cover',
              style: 'border-radius:4px',
              previewDisabled: true
            })
          : h('div', { style: 'width:40px;height:40px;border-radius:4px;background:#eee' }),
        h('div', { style: 'min-width:0' }, [
          h('div', { style: 'font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px' }, title),
          h('div', { style: 'font-size:11px;opacity:0.55' }, id)
        ])
      ])
    }
  },
  {
    title: '专属回复',
    key: 'reply',
    ellipsis: { tooltip: true },
    render: (r) => r.reply || r.reply_content || ''
  },
  {
    title: '操作',
    key: 'a',
    width: 140,
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
                title: '删除商品回复',
                content: `确定删除商品 ${r.item_id} 的专属回复吗？`,
                positiveText: '删除',
                negativeText: '取消',
                onPositiveClick: async () => {
                  await deleteItemReply(rowId(r))
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

async function loadItems(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    itemOptions.value = []
    itemMap.value = {}
    return
  }
  try {
    const list = await getItems(cookieId)
    const map: Record<string, ItemRow> = {}
    itemOptions.value = list.map((it) => {
      const id = String(it.item_id || it.id || '')
      const title = String(it.title || it.item_title || id)
      const pic = String(it.item_pic || it.pic_url || (it as any).main_image || '')
      map[id] = it
      return {
        label: title,
        value: id,
        pic,
        title
      }
    })
    itemMap.value = map
  } catch {
    itemOptions.value = []
    itemMap.value = {}
  }
}

function renderItemLabel(option: SelectOption): any {
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
            style:
              'width:36px;height:36px;border-radius:4px;background:#eee;flex-shrink:0'
          }),
      h('div', { style: 'min-width:0' }, [
        h('div', { style: 'font-size:13px;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:280px' }, title),
        h('div', { style: 'font-size:11px;opacity:0.6' }, id)
      ])
    ]
  )
}

function openCreate(): void {
  editing.value = null
  form.value = { item_ids: [], reply: '', title: '' }
  showModal.value = true
  void loadItems()
}

function openEdit(r: ItemReplyRow): void {
  editing.value = { ...r }
  form.value = {
    item_ids: [String(r.item_id || '')].filter(Boolean),
    reply: String(r.reply || r.reply_content || ''),
    title: String(r.title || r.item_title || '')
  }
  showModal.value = true
  void loadItems()
}

async function load(): Promise<void> {
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    rows.value = []
    return
  }
  loading.value = true
  try {
    await loadItems()
    rows.value = await getItemReplies(cookieId)
  } catch (e: any) {
    message.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onSave(): Promise<void> {
  await formRef.value?.validate()
  const cookieId = accountStore.activeCookieId
  if (!cookieId) {
    message.warning('请先选择账号')
    return
  }
  if (!form.value.item_ids.length) {
    message.warning('请选择至少一个商品')
    return
  }
  try {
    if (editing.value) {
      await updateItemReply(rowId(editing.value), {
        cookie_id: cookieId,
        item_id: form.value.item_ids[0],
        reply: form.value.reply,
        title: form.value.title
      })
      message.success('已更新')
    } else {
      await addItemReply({
        cookie_id: cookieId,
        item_id: form.value.item_ids.join(','),
        reply: form.value.reply,
        title: form.value.title
      })
      message.success(`已为 ${form.value.item_ids.length} 个商品保存回复`)
    }
    showModal.value = false
    await load()
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <n-card title="商品回复" size="small">
    <AccountTabs :show-unread="false" @change="load" />
    <n-space style="margin-bottom: 12px">
      <n-button type="primary" @click="openCreate">新增回复</n-button>
      <n-button secondary :loading="loading" @click="load">刷新</n-button>
    </n-space>
    <n-data-table :loading="loading" :columns="columns" :data="rows" size="small" :bordered="false" />
  </n-card>

  <n-modal
    v-model:show="showModal"
    preset="card"
    :title="editing ? '编辑商品回复' : '新增商品回复'"
    style="width: 560px"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="88">
      <n-form-item label="指定商品">
        <n-select
          v-model:value="form.item_ids"
          multiple
          filterable
          tag
          clearable
          placeholder="可多选，也可输入商品ID（带缩略图）"
          :options="itemOptions"
          :render-label="renderItemLabel"
          :disabled="!!editing"
          style="width: 100%"
        />
      </n-form-item>
      <n-form-item label="标题">
        <n-input v-model:value="form.title" placeholder="可选备注标题" />
      </n-form-item>
      <n-form-item label="回复内容" path="reply">
        <n-input v-model:value="form.reply" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showModal = false">取消</n-button>
        <n-button type="primary" @click="onSave">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
