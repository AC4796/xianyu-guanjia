<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span class="font-medium">商品专属回复</span>
          <ElSpace>
            <ElSelect
              v-model="cookieId"
              placeholder="账号"
              style="width: 200px"
              clearable
              filterable
              @change="onAccountChange"
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
            <ElButton type="primary" @click="openEdit()">新增</ElButton>
            <ElButton :loading="loading" @click="loadData">刷新</ElButton>
          </ElSpace>
        </div>
      </template>
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        class="mb-3"
        title="买家咨询对应商品时，优先发送此处配置的回复；账号需保持在线。"
      />
      <ElTable :data="list" v-loading="loading" stripe border>
        <ElTableColumn prop="cookie_id" label="账号" width="120" />
        <ElTableColumn prop="item_id" label="商品ID" width="140" />
        <ElTableColumn prop="title" label="标题" min-width="160" show-overflow-tooltip />
        <ElTableColumn prop="reply" label="回复" min-width="200" show-overflow-tooltip />
        <ElTableColumn label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton link type="danger" @click="remove(row.id)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog v-model="visible" :title="form.id ? '编辑' : '新增'" width="560px">
      <ElForm label-width="90px">
        <ElFormItem label="账号">
          <ElSelect v-model="form.cookie_id" style="width: 100%" @change="loadProducts">
            <ElOption
              v-for="a in accounts"
              :key="a.id"
              :label="a.nickname || a.remark || a.id"
              :value="a.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="选择商品">
          <ElSelect
            v-model="selectedItems"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="从商品列表多选"
            style="width: 100%"
            :disabled="!!form.id"
          >
            <ElOption
              v-for="p in products"
              :key="p.item_id"
              :label="`${p.item_title || p.title || p.item_id}`"
              :value="p.item_id"
            >
              <div class="flex items-center gap-2 max-w-full">
                <ElImage
                  v-if="p.item_pic"
                  :src="p.item_pic"
                  style="width: 28px; height: 28px; border-radius: 4px"
                  fit="cover"
                />
                <span class="truncate">{{ p.item_title || p.title || p.item_id }}</span>
              </div>
            </ElOption>
          </ElSelect>
          <div class="text-xs text-g-400 mt-1">编辑时仅改当前商品回复；新增可多选批量写入同一回复</div>
        </ElFormItem>
        <ElFormItem label="回复">
          <ElInput v-model="form.reply" type="textarea" :rows="4" placeholder="支持变量 {send_user_name}" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="visible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import {
    getAccountDetails,
    getItemReplies,
    addItemReply,
    updateItemReply,
    deleteItemReply,
    getItems,
    type ItemReply,
    type Item
  } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'ItemReplies' })

  const loading = ref(false)
  const saving = ref(false)
  const list = ref<ItemReply[]>([])
  const accounts = ref<Array<{ id: string; remark?: string; nickname?: string; avatar_url?: string }>>([])
  const cookieId = ref('')
  const visible = ref(false)
  const products = ref<Item[]>([])
  const selectedItems = ref<string[]>([])
  const form = reactive<Partial<ItemReply>>({
    cookie_id: '',
    item_id: '',
    title: '',
    reply: ''
  })

  async function loadProducts() {
    const cid = form.cookie_id || cookieId.value
    if (!cid) {
      products.value = []
      return
    }
    products.value = await getItems(cid)
  }

  async function loadData() {
    loading.value = true
    try {
      if (!accounts.value.length) accounts.value = await getAccountDetails()
      list.value = await getItemReplies(cookieId.value || undefined)
    } finally {
      loading.value = false
    }
  }

  function onAccountChange() {
    loadData()
  }

  async function openEdit(row?: ItemReply) {
    Object.assign(form, {
      id: undefined,
      cookie_id: cookieId.value || accounts.value[0]?.id || '',
      item_id: '',
      title: '',
      reply: '',
      ...row
    })
    selectedItems.value = row?.item_id ? [row.item_id] : []
    visible.value = true
    await loadProducts()
  }

  async function save() {
    if (!form.cookie_id || !form.reply) {
      ElMessage.warning('请填写账号和回复内容')
      return
    }
    if (!form.id && !selectedItems.value.length) {
      ElMessage.warning('请选择商品')
      return
    }
    saving.value = true
    try {
      if (form.id) {
        await updateItemReply(form.id, {
          ...form,
          item_id: selectedItems.value[0] || form.item_id
        })
      } else {
        await addItemReply({
          cookie_id: form.cookie_id,
          item_id: selectedItems.value.join(','),
          reply: form.reply,
          title: form.title
        })
      }
      ElMessage.success('已保存')
      visible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  async function remove(id: string) {
    await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
    await deleteItemReply(id)
    ElMessage.success('已删除')
    loadData()
  }

  onMounted(loadData)
</script>
