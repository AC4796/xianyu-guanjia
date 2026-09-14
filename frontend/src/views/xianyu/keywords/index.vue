<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span class="font-medium">关键词回复</span>
          <ElSpace>
            <ElSelect v-model="cookieId" placeholder="选择账号" style="width: 220px" @change="loadKeywords">
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
            <ElButton type="primary" :disabled="!cookieId" @click="openEdit()">新增</ElButton>
            <ElButton :disabled="!cookieId" @click="openDefault">默认回复</ElButton>
          </ElSpace>
        </div>
      </template>

      <ElAlert
        type="warning"
        :closable="false"
        show-icon
        class="mb-3"
        title="自动回复生效条件：账号在「账号管理」中启用并保持在线；买家消息包含关键词（子串匹配）。绑定商品后仅对该商品会话生效。"
      />

      <ElTable :data="keywords" v-loading="loading" stripe border>
        <ElTableColumn prop="keyword" label="关键词" min-width="140" />
        <ElTableColumn prop="reply" label="回复内容" min-width="220" show-overflow-tooltip />
        <ElTableColumn label="绑定商品" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ productLabel(row.item_id) || row.item_id || '全部商品' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton link type="danger" @click="remove(row)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog v-model="editVisible" :title="editing ? '编辑关键词' : '新增关键词'" width="560px">
      <ElForm label-width="90px">
        <ElFormItem label="关键词"><ElInput v-model="form.keyword" placeholder="买家消息包含即触发" /></ElFormItem>
        <ElFormItem label="回复"><ElInput v-model="form.reply" type="textarea" :rows="4" /></ElFormItem>
        <ElFormItem label="绑定商品">
          <ElSelect
            v-model="form.item_id"
            clearable
            filterable
            placeholder="不选=全部商品通用"
            style="width: 100%"
          >
            <ElOption
              v-for="p in products"
              :key="p.item_id"
              :label="p.item_title || p.title || p.item_id"
              :value="p.item_id"
            >
              <div class="flex items-center gap-2">
                <ElImage
                  v-if="p.item_pic"
                  :src="p.item_pic"
                  style="width: 28px; height: 28px"
                  fit="cover"
                />
                <span class="truncate">{{ p.item_title || p.title || p.item_id }}</span>
              </div>
            </ElOption>
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="defaultVisible" title="默认回复" width="520px">
      <ElForm label-width="100px" v-if="defaultForm">
        <ElFormItem label="启用"><ElSwitch v-model="defaultForm.enabled" /></ElFormItem>
        <ElFormItem label="仅回复一次"><ElSwitch v-model="defaultForm.reply_once" /></ElFormItem>
        <ElFormItem label="内容">
          <ElInput v-model="defaultForm.reply_content" type="textarea" :rows="4" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton type="primary" :loading="saving" @click="saveDefault">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import {
    getAccountDetails,
    getKeywords,
    addKeyword,
    updateKeyword,
    deleteKeyword,
    getDefaultReply,
    updateDefaultReply,
    getItems,
    type Keyword,
    type DefaultReply,
    type Item
  } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'Keywords' })

  const loading = ref(false)
  const saving = ref(false)
  const accounts = ref<Array<{ id: string; remark?: string; nickname?: string; avatar_url?: string }>>([])
  const cookieId = ref('')
  const keywords = ref<Keyword[]>([])
  const products = ref<Item[]>([])
  const editVisible = ref(false)
  const editing = ref(false)
  const oldKey = reactive({ keyword: '', item_id: '' })
  const form = reactive({ keyword: '', reply: '', item_id: '' })
  const defaultVisible = ref(false)
  const defaultForm = ref<DefaultReply | null>(null)

  const productMap = computed(() => {
    const m: Record<string, Item> = {}
    products.value.forEach((p) => {
      m[p.item_id] = p
    })
    return m
  })

  function productLabel(itemId?: string) {
    if (!itemId) return ''
    const p = productMap.value[itemId]
    return p?.item_title || p?.title || ''
  }

  async function loadProducts() {
    if (!cookieId.value) {
      products.value = []
      return
    }
    products.value = await getItems(cookieId.value)
  }

  async function init() {
    accounts.value = await getAccountDetails()
    if (accounts.value.length) {
      cookieId.value = accounts.value[0].id
      await loadKeywords()
    }
  }

  async function loadKeywords() {
    if (!cookieId.value) return
    loading.value = true
    try {
      ;[keywords.value] = await Promise.all([getKeywords(cookieId.value), loadProducts()])
    } finally {
      loading.value = false
    }
  }

  function openEdit(row?: Keyword) {
    editing.value = !!row
    form.keyword = row?.keyword || ''
    form.reply = row?.reply || ''
    form.item_id = row?.item_id || ''
    oldKey.keyword = row?.keyword || ''
    oldKey.item_id = row?.item_id || ''
    editVisible.value = true
    loadProducts()
  }

  async function save() {
    if (!cookieId.value || !form.keyword) {
      ElMessage.warning('请填写关键词')
      return
    }
    saving.value = true
    try {
      const payload = { ...form, item_id: form.item_id || '' }
      if (editing.value) {
        await updateKeyword(cookieId.value, oldKey.keyword, oldKey.item_id, payload)
      } else {
        await addKeyword(cookieId.value, payload)
      }
      ElMessage.success('已保存（账号在线时买家消息命中关键词会自动回复）')
      editVisible.value = false
      loadKeywords()
    } finally {
      saving.value = false
    }
  }

  async function remove(row: Keyword) {
    await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
    await deleteKeyword(cookieId.value, row.keyword, row.item_id || '')
    ElMessage.success('已删除')
    loadKeywords()
  }

  async function openDefault() {
    defaultForm.value = await getDefaultReply(cookieId.value)
    defaultVisible.value = true
  }

  async function saveDefault() {
    if (!defaultForm.value) return
    saving.value = true
    try {
      await updateDefaultReply(cookieId.value, defaultForm.value)
      ElMessage.success('已保存')
      defaultVisible.value = false
    } finally {
      saving.value = false
    }
  }

  onMounted(init)
</script>
