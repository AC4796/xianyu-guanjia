<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NForm,
  NFormItem,
  NImage,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NTag,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  addDeliveryRule,
  deleteDeliveryRule,
  getCards,
  getDeliveryRules,
  type CardRow,
  type DeliveryRule
} from '../api/delivery'
import { getItems, type ItemRow } from '../api/items'

const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const accountStore = useAccountStore()
const loading = ref(false)
const cards = ref<CardRow[]>([])
const rules = ref<DeliveryRule[]>([])
const items = ref<ItemRow[]>([])
const showRuleModal = ref(false)
const ruleForm = ref({ keyword: '', card_id: null as number | null })

const cardOptions = computed(() =>
  cards.value.map((c) => {
    let stock = ''
    if (c.type === 'data') {
      const n = String(c.data_content || c.data || '')
        .split(/\r?\n/)
        .map((x) => x.trim())
        .filter(Boolean).length
      stock = ` · 剩${n}`
    }
    return {
      label: `#${c.id} ${c.name || '未命名'}（${c.type}${stock}）`,
      value: Number(c.id)
    }
  })
)

function cardName(id: unknown): string {
  const c = cards.value.find((x) => String(x.id) === String(id))
  if (!c) return String(id || '-')
  return `${c.name || '未命名'} (#${c.id})`
}

function stockOf(c: CardRow): string {
  if (c.type !== 'data') return '-'
  const n = String(c.data_content || c.data || '')
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean).length
  return String(n)
}

function itemPicOf(id: string): string {
  const it = items.value.find((x) => String(x.item_id || x.id) === id)
  if (!it) return ''
  return String((it as any).item_pic || it.pic_url || (it as any).main_image || '')
}

function boundThumbs(c: CardRow): Array<{ src: string; title: string }> {
  const bounds = (c.bound_items as Array<{ item_id?: string; title?: string; item_pic?: string }>) || []
  if (bounds.length) {
    return bounds
      .map((b) => ({
        src: String(b.item_pic || itemPicOf(String(b.item_id || '')) || ''),
        title: String(b.title || b.item_id || '')
      }))
      .filter((x) => x.src)
      .slice(0, 4)
  }
  const ids = ((c.item_ids as string[]) || []).map(String)
  return ids
    .map((id) => ({ src: itemPicOf(id), title: id }))
    .filter((x) => x.src)
    .slice(0, 4)
}

function ruleThumbs(r: DeliveryRule): Array<{ src: string; title: string }> {
  const card = cards.value.find((x) => String(x.id) === String(r.card_id))
  if (card) {
    const fromCard = boundThumbs(card)
    if (fromCard.length) return fromCard
  }
  const iid = String(r.item_id || '').trim()
  if (iid) {
    const src = itemPicOf(iid)
    if (src) return [{ src, title: iid }]
  }
  // 关键词恰好是商品 ID / 标题命中
  const kw = String(r.keyword || '').trim()
  if (kw) {
    const byId = items.value.find((x) => String(x.item_id || x.id) === kw)
    if (byId) {
      const src = String((byId as any).item_pic || byId.pic_url || '')
      if (src) return [{ src, title: String(byId.title || byId.item_title || kw) }]
    }
    const hit = items.value.find((x) => String(x.title || x.item_title || '').includes(kw))
    if (hit) {
      const src = String((hit as any).item_pic || hit.pic_url || '')
      if (src) return [{ src, title: String(hit.title || hit.item_title || kw) }]
    }
  }
  // 图片类型库存：内容本身可能是图
  if (card && String(card.type) === 'image') {
    const raw = String(card.data_content || card.data || card.content || '')
    const urls = raw
      .split(/\r?\n/)
      .map((x) => x.trim())
      .filter((x) => /^https?:\/\//i.test(x) || x.startsWith('data:image'))
    return urls.slice(0, 4).map((src) => ({ src, title: String(card.name || '图片') }))
  }
  return []
}

function renderThumbs(list: Array<{ src: string; title: string }>) {
  if (!list.length) return h('span', { style: 'color:#aaa' }, '-')
  return h(
    NSpace,
    { size: 4, align: 'center' },
    () =>
      list.map((t, i) =>
        h(NImage, {
          key: `${i}-${t.src}`,
          src: t.src,
          width: 36,
          height: 36,
          objectFit: 'cover',
          style: 'border-radius:4px;cursor:zoom-in',
          alt: t.title,
          lazy: true
        })
      )
  )
}

const cardColumns: DataTableColumns<CardRow> = [
  {
    title: '缩略图',
    key: 'thumbs',
    width: 160,
    render: (r) => renderThumbs(boundThumbs(r))
  },
  { title: 'ID', key: 'id', width: 70 },
  { title: '名称', key: 'name' },
  {
    title: '类型',
    key: 'type',
    width: 90,
    render: (r) =>
      ({ data: '卡密', text: '文本', image: '图片', api: 'API' } as Record<string, string>)[
        String(r.type)
      ] || String(r.type)
  },
  { title: '剩余库存', key: 'stock', width: 100, render: (r) => stockOf(r) },
  {
    title: '启用',
    key: 'enabled',
    width: 70,
    render: (r) =>
      h(NTag, { size: 'small', type: r.enabled === false ? 'default' : 'success' }, () =>
        r.enabled === false ? '关' : '开'
      )
  }
]

const ruleColumns: DataTableColumns<DeliveryRule> = [
  {
    title: '商品图',
    key: 'pic',
    width: 160,
    render: (r) => renderThumbs(ruleThumbs(r))
  },
  { title: '触发关键词', key: 'keyword' },
  {
    title: '绑定库存',
    key: 'card_id',
    render: (r) => cardName(r.card_id)
  },
  {
    title: '已发次数',
    key: 'delivery_times',
    width: 90,
    render: (r) => String(r.delivery_times ?? 0)
  },
  {
    title: '操作',
    key: 'a',
    width: 90,
    render: (r) =>
      h(
        NButton,
        {
          size: 'tiny',
          type: 'error',
          secondary: true,
          onClick: () => {
            dialog.warning({
              title: '删除规则',
              content: `确定删除关键词「${r.keyword}」的发货规则？`,
              positiveText: '删除',
              negativeText: '取消',
              onPositiveClick: async () => {
                await deleteDeliveryRule(r.id!)
                message.success('已删除')
                await load()
              }
            })
          }
        },
        () => '删除'
      )
  }
]

async function load(): Promise<void> {
  loading.value = true
  try {
    const cid = accountStore.activeCookieId || undefined
    const [cardList, ruleList, itemList] = await Promise.all([
      getCards(),
      getDeliveryRules(cid),
      cid ? getItems(cid).catch(() => [] as ItemRow[]) : Promise.resolve([] as ItemRow[])
    ])
    cards.value = cardList
    rules.value = ruleList
    items.value = itemList
  } catch (e: any) {
    message.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openRule(): void {
  if (!cards.value.length) {
    message.warning('请先在「卡密库存」里创建库存')
    void router.push({ name: 'cards-inventory' })
    return
  }
  ruleForm.value = {
    keyword: '',
    card_id: Number(cards.value[0].id) || null
  }
  showRuleModal.value = true
}

async function saveRule(): Promise<void> {
  const kw = ruleForm.value.keyword.trim()
  if (!kw) {
    message.warning('请填写触发关键词（建议填商品标题里的关键词）')
    return
  }
  if (!ruleForm.value.card_id) {
    message.warning('请选择要发放的卡密库存')
    return
  }
  await addDeliveryRule({
    keyword: kw,
    card_id: ruleForm.value.card_id,
    enabled: true
  })
  message.success('发货规则已保存：付款后命中关键词即自动发对应库存')
  showRuleModal.value = false
  await load()
}

onMounted(() => void load())
watch(
  () => accountStore.activeCookieId,
  () => void load()
)
</script>

<template>
  <n-space vertical :size="16">
    <n-card title="发货规则（绑定卡密库存）" size="small">
      <AccountTabs @change="load" />
      <n-text depth="3" style="display: block; margin: 8px 0 12px; font-size: 13px">
        买家付款后，订单商品标题命中「触发关键词」时，自动发放对应库存。点击缩略图可放大查看。
      </n-text>
      <n-space style="margin-bottom: 12px">
        <n-button type="primary" size="small" @click="openRule">新增规则</n-button>
        <n-button size="small" quaternary @click="load">刷新</n-button>
      </n-space>
      <n-data-table :loading="loading" :columns="ruleColumns" :data="rules" size="small" />
      <n-empty v-if="!loading && !rules.length" description="暂无发货规则" style="margin-top: 16px" />
    </n-card>

    <n-card title="可用库存一览" size="small">
      <n-data-table :loading="loading" :columns="cardColumns" :data="cards" size="small" />
      <n-empty v-if="!loading && !cards.length" description="请先去「卡密库存」创建" style="margin-top: 16px" />
    </n-card>

    <n-modal v-model:show="showRuleModal" preset="card" title="新增发货规则" style="width: 480px">
      <n-form label-placement="left" label-width="100">
        <n-form-item label="触发关键词">
          <n-input
            v-model:value="ruleForm.keyword"
            placeholder="商品标题中包含的关键词，如：安装包"
          />
        </n-form-item>
        <n-form-item label="发放库存">
          <n-select v-model:value="ruleForm.card_id" :options="cardOptions" placeholder="选择卡密库存" />
        </n-form-item>
      </n-form>
      <n-space justify="end">
        <n-button @click="showRuleModal = false">取消</n-button>
        <n-button type="primary" @click="saveRule">保存</n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>
