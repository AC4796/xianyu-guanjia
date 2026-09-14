<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">卡券管理</span>
          <ElSpace>
            <ElButton type="primary" @click="openEdit()">新增卡券</ElButton>
            <ElButton :loading="loading" @click="loadData">刷新</ElButton>
          </ElSpace>
        </div>
      </template>
      <ElTable :data="list" v-loading="loading" stripe border>
        <ElTableColumn prop="id" label="ID" width="80" />
        <ElTableColumn prop="name" label="名称" min-width="140" />
        <ElTableColumn prop="type" label="类型" width="100" />
        <ElTableColumn prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <ElTableColumn label="启用" width="90">
          <template #default="{ row }">
            <ElTag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton link type="danger" @click="remove(row.id!)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog v-model="visible" :title="form.id ? '编辑卡券' : '新增卡券'" width="560px">
      <ElForm label-width="90px">
        <ElFormItem label="名称"><ElInput v-model="form.name" /></ElFormItem>
        <ElFormItem label="类型">
          <ElSelect v-model="form.type">
            <ElOption label="文本" value="text" />
            <ElOption label="数据" value="data" />
            <ElOption label="API" value="api" />
            <ElOption label="图片" value="image" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="描述"><ElInput v-model="form.description" /></ElFormItem>
        <ElFormItem label="文本内容" v-if="form.type === 'text'">
          <ElInput v-model="form.text_content" type="textarea" :rows="4" />
        </ElFormItem>
        <ElFormItem label="数据内容" v-if="form.type === 'data'">
          <ElInput v-model="form.data_content" type="textarea" :rows="4" />
        </ElFormItem>
        <ElFormItem label="图片URL" v-if="form.type === 'image'">
          <ElInput v-model="form.image_url" />
        </ElFormItem>
        <ElFormItem label="启用"><ElSwitch v-model="form.enabled" /></ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="visible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import { getCards, createCard, updateCard, deleteCard, type CardData } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'Cards' })

  const loading = ref(false)
  const saving = ref(false)
  const list = ref<CardData[]>([])
  const visible = ref(false)
  const form = reactive<Partial<CardData>>({
    name: '',
    type: 'text',
    description: '',
    text_content: '',
    data_content: '',
    image_url: '',
    enabled: true
  })

  async function loadData() {
    loading.value = true
    try {
      list.value = await getCards()
    } finally {
      loading.value = false
    }
  }

  function openEdit(row?: CardData) {
    Object.assign(form, {
      id: undefined,
      name: '',
      type: 'text',
      description: '',
      text_content: '',
      data_content: '',
      image_url: '',
      enabled: true,
      ...row
    })
    visible.value = true
  }

  async function save() {
    if (!form.name) {
      ElMessage.warning('请填写名称')
      return
    }
    saving.value = true
    try {
      if (form.id) await updateCard(form.id, form)
      else await createCard(form)
      ElMessage.success('已保存')
      visible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  async function remove(id: number) {
    await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
    await deleteCard(id)
    ElMessage.success('已删除')
    loadData()
  }

  onMounted(loadData)
</script>
