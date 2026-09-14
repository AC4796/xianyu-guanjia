<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">发货规则</span>
          <ElSpace>
            <ElButton type="primary" @click="openEdit()">新增规则</ElButton>
            <ElButton :loading="loading" @click="loadData">刷新</ElButton>
          </ElSpace>
        </div>
      </template>
      <ElTable :data="list" v-loading="loading" stripe border>
        <ElTableColumn prop="id" label="ID" width="70" />
        <ElTableColumn prop="keyword" label="匹配关键词" min-width="140" />
        <ElTableColumn prop="card_name" label="卡券" min-width="120">
          <template #default="{ row }">{{ row.card_name || row.card_id }}</template>
        </ElTableColumn>
        <ElTableColumn prop="delivery_count" label="发货数量" width="100" />
        <ElTableColumn prop="description" label="描述" min-width="140" show-overflow-tooltip />
        <ElTableColumn label="启用" width="90">
          <template #default="{ row }">
            <ElSwitch :model-value="row.enabled" @change="(v) => toggle(row, !!v)" />
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton link type="danger" @click="remove(row.id)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog v-model="visible" :title="form.id ? '编辑规则' : '新增规则'" width="520px">
      <ElForm label-width="100px">
        <ElFormItem label="关键词"><ElInput v-model="form.keyword" /></ElFormItem>
        <ElFormItem label="卡券">
          <ElSelect v-model="form.card_id" style="width: 100%">
            <ElOption v-for="c in cards" :key="c.id" :label="c.name" :value="c.id!" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="发货数量">
          <ElInputNumber v-model="form.delivery_count" :min="1" />
        </ElFormItem>
        <ElFormItem label="描述"><ElInput v-model="form.description" /></ElFormItem>
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
  import {
    getDeliveryRules,
    addDeliveryRule,
    updateDeliveryRule,
    deleteDeliveryRule,
    getCards,
    type DeliveryRule,
    type CardData
  } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'DeliveryRules' })

  const loading = ref(false)
  const saving = ref(false)
  const list = ref<DeliveryRule[]>([])
  const cards = ref<CardData[]>([])
  const visible = ref(false)
  const form = reactive<Partial<DeliveryRule>>({
    keyword: '',
    card_id: undefined,
    delivery_count: 1,
    description: '',
    enabled: true
  })

  async function loadData() {
    loading.value = true
    try {
      ;[list.value, cards.value] = await Promise.all([getDeliveryRules(), getCards()])
    } finally {
      loading.value = false
    }
  }

  function openEdit(row?: DeliveryRule) {
    Object.assign(form, {
      id: undefined,
      keyword: '',
      card_id: cards.value[0]?.id,
      delivery_count: 1,
      description: '',
      enabled: true,
      ...row
    })
    visible.value = true
  }

  async function save() {
    if (!form.keyword || !form.card_id) {
      ElMessage.warning('请填写完整')
      return
    }
    saving.value = true
    try {
      const payload = {
        keyword: form.keyword,
        card_id: form.card_id,
        delivery_count: form.delivery_count || 1,
        description: form.description,
        enabled: form.enabled ?? true
      }
      if (form.id) await updateDeliveryRule(form.id, payload)
      else await addDeliveryRule(payload)
      ElMessage.success('已保存')
      visible.value = false
      loadData()
    } finally {
      saving.value = false
    }
  }

  async function toggle(row: DeliveryRule, enabled: boolean) {
    await updateDeliveryRule(row.id, { ...row, enabled })
    ElMessage.success('已更新')
    loadData()
  }

  async function remove(id: number) {
    await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
    await deleteDeliveryRule(id)
    ElMessage.success('已删除')
    loadData()
  }

  onMounted(loadData)
</script>
