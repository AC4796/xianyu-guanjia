<template>
  <div class="art-full-height p-4">
    <ElCard shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">用户管理</span>
          <ElButton :loading="loading" @click="loadData">刷新</ElButton>
        </div>
      </template>
      <ElTable :data="list" v-loading="loading" stripe border>
        <ElTableColumn prop="user_id" label="ID" width="80" />
        <ElTableColumn prop="username" label="用户名" min-width="140" />
        <ElTableColumn prop="email" label="邮箱" min-width="180" />
        <ElTableColumn label="管理员" width="100">
          <template #default="{ row }">
            <ElTag :type="row.is_admin ? 'danger' : 'info'">{{ row.is_admin ? '是' : '否' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="120">
          <template #default="{ row }">
            <ElButton link type="danger" :disabled="row.is_admin" @click="remove(row.user_id)">
              删除
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { getUsers, deleteUser, type User } from '@/api/xy'
  import { ElMessage, ElMessageBox } from 'element-plus'

  defineOptions({ name: 'AdminUsers' })

  const loading = ref(false)
  const list = ref<User[]>([])

  async function loadData() {
    loading.value = true
    try {
      const res = await getUsers()
      list.value = res.data || []
    } finally {
      loading.value = false
    }
  }

  async function remove(id: number) {
    await ElMessageBox.confirm('确认删除该用户？', '提示', { type: 'warning' })
    await deleteUser(id)
    ElMessage.success('已删除')
    loadData()
  }

  onMounted(loadData)
</script>
