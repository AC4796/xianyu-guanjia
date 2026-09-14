<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { NCard, NText } from 'naive-ui'
import { useAccountStore } from '../stores/account'

const route = useRoute()
const accountStore = useAccountStore()

const meta = computed(() => {
  const map: Record<string, { title: string; desc: string }> = {
    home: { title: '首页', desc: '工作台概览，后续会展示当前账号的核心数据。' },
    messages: { title: '消息', desc: '买家消息与会话将在此处理。' },
    orders: { title: '订单管理', desc: '查看与处理销售订单。' },
    'my-orders': { title: '我的订单管理', desc: '管理与当前账号相关的订单明细。' },
    'ship-templates': { title: '发货模板', desc: '配置自动发货文案与模板。' },
    items: { title: '商品管理', desc: '管理当前账号商品。' },
    marketing: { title: '营销管理', desc: '营销相关功能将在此扩展。' },
    accounts: { title: '账号管理', desc: '管理已绑定的闲鱼账号。' },
    'notify-settings': { title: '通知设置', desc: '配置通知渠道与提醒方式。' },
    settings: { title: '系统设置', desc: '客户端与业务相关配置。' }
  }
  const key = String(route.name || 'home')
  return (
    map[key] || {
      title: String(route.meta.title || '模块'),
      desc: '功能开发中。'
    }
  )
})
</script>

<template>
  <n-card :title="meta.title" size="small" :bordered="true">
    <n-text depth="3">{{ meta.desc }}</n-text>
    <div style="margin-top: 12px">
      <n-text depth="3">当前 Cookie ID：{{ accountStore.activeCookieId || '未选择' }}</n-text>
    </div>
  </n-card>
</template>
