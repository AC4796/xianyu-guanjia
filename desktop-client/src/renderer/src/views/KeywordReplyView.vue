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
  NRadio,
  NRadioGroup,
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
  addKeyword,
  deleteKeyword,
  getKeywords,
  updateKeyword,
  type KeywordRow
} from '../api/keywords'
import { getItems } from '../api/items'

const message = useMessage()
const dialog = useDialog()
const accountStore = useAccountStore()
const loading = ref(false)
const rows = ref<KeywordRow[]>([])
const showModal = ref(false)
const editing = ref<KeywordRow | null>(null)
const formRef = ref<FormInst | null>(null)
const itemOptions = ref<SelectOption[]>([])
const form = ref({
  keyword: '',
  reply: '',
  scope: 'all' as 'all' | 'item',
  item_id: ''
})

function renderItemLabel(option: SelectOption): any {
  const pic = String((option as any).pic || '')
  const title = String((option as any).title || option.label || '')
  const id = String(option.value || '')
  return h('div', { style: 'display:flex;align-items:center;gap:8px;padding:2px 0' }, [
    pic
      ? h(NImage, {
          src: pic,
          width: 36,
          height: 36,
          objectFit: 'cover',
          style: 'border-radius:4px;flex-shrink:0',
          previewDisabled: true
        })
      : h('div', { style: 'width:36px;height:36px;border-radius:4px;background:#eee;flex-shrink:0' }),
    h('div', { style: 'min-width:0' }, [
      h(
        'div',
        {
          style:
            'font-size:13px;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:280px'
        },
        title
      ),
      h('div', { style: 'font-size:11px;opacity:0.6' }, id)
    ])
  ])
}

const rules: FormRules = {
  keyword: { required: true, message: '请输入关键词', trigger: 'blur' },
  reply: { required: true, message: '请输入回复内容', trigger: 'blur' }
}

function bindScopeLabel(r: KeywordRow): string {
  return r.item_id ? `指定：${r.item_id}` : '全部商品'
}

const columns: DataTableColumns<KeywordRow> = [
  { title: '关键词', key: 'keyword', width: 140, ellipsis: { tooltip: true } },
  { title: '回复内容', key: 'reply', ellipsis: { tooltip: true } },
  {
    title: '绑定商品',
    key: 'item_id',
    width: 160,
    render: (r) => bindScopeLabel(r)
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
                title: '删除关键词',
                content: `确定删除「${r.keyword}」吗？`,
                positiveText: '删除',
                negativeText: '取消',
                onPositiveClick: async () => {
                  const cookieId = accountStore.activeCookieId
                  if (!cookieId) return
                  await deleteKeyword(cookieId, r.keyword, r.item_id || '')
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
    return
  }
  try {
    const list = await getItems(cookieId)
    itemOptions.value = list.map((it) => {
      const id = String(it.item_id || it.id || '')
      const title = String(it.title || it.item_title || id)
      const pic = String(it.item_pic || it.pic_url || '')
      return {
        label: title,
        value: id,
        pic,
        title
      }
    })
  } catch {
    itemOptions.value = []
  }
}

function openCreate(): void {
  editing.value = null
  form.value = { keyword: '', reply: '', scope: 'all', item_id: '' }
  showModal.value = true
  void loadItems()
}

function openEdit(r: KeywordRow): void {
  editing.value = { ...r }
  form.value = {
    keyword: r.keyword,
    reply: r.reply || '',
    scope: r.item_id ? 'item' : 'all',
    item_id: r.item_id || ''
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
    rows.value = await getKeywords(cookieId)
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
  if (form.value.scope === 'item' && !form.value.item_id.trim()) {
    message.warning('请选择或填写要绑定的商品')
    return
  }
  const payload = {
    keyword: form.value.keyword,
    reply: form.value.reply,
    item_id: form.value.scope === 'all' ? '' : form.value.item_id.trim()
  }
  try {
    if (editing.value) {
      const res = await updateKeyword(
        cookieId,
        editing.value.keyword,
        editing.value.item_id || '',
        payload
      )
      if (!res.success) {
        message.error(res.message || '更新失败')
        return
      }
      message.success('已更新')
    } else {
      const res = await addKeyword(cookieId, payload)
      if (!res.success) {
        message.error(res.message || '添加失败')
        return
      }
      message.success('已添加')
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
  <n-card title="关键词回复" size="small">
    <AccountTabs :show-unread="false" @change="load" />
    <n-space style="margin-bottom: 12px">
      <n-button type="primary" @click="openCreate">新增关键词</n-button>
      <n-button secondary :loading="loading" @click="load">刷新</n-button>
    </n-space>
    <n-data-table :loading="loading" :columns="columns" :data="rows" size="small" :bordered="false" />
  </n-card>

  <n-modal
    v-model:show="showModal"
    preset="card"
    :title="editing ? '编辑关键词' : '新增关键词'"
    style="width: 520px"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="88">
      <n-form-item label="关键词" path="keyword">
        <n-input v-model:value="form.keyword" placeholder="买家消息匹配关键词" />
      </n-form-item>
      <n-form-item label="回复内容" path="reply">
        <n-input v-model:value="form.reply" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" />
      </n-form-item>
      <n-form-item label="绑定范围">
        <n-radio-group v-model:value="form.scope">
          <n-radio value="all">全部商品</n-radio>
          <n-radio value="item">指定商品</n-radio>
        </n-radio-group>
      </n-form-item>
      <n-form-item v-if="form.scope === 'item'" label="指定商品">
        <n-select
          v-model:value="form.item_id"
          filterable
          tag
          clearable
          placeholder="选择商品或直接输入商品ID（带缩略图）"
          :options="itemOptions"
          :render-label="renderItemLabel"
          style="width: 100%"
        />
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
