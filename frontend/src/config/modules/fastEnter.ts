/**
 * 快速入口配置 — 仅保留闲鱼管家业务入口
 */
import type { FastEnterConfig } from '@/types/config'

const fastEnterConfig: FastEnterConfig = {
  minWidth: 1200,
  applications: [
    {
      name: '工作台',
      description: '系统概览与数据统计',
      icon: 'ri:pie-chart-line',
      iconColor: '#377dff',
      enabled: true,
      order: 1,
      routeName: 'Console'
    },
    {
      name: '闲鱼账号',
      description: '账号绑定与监听状态',
      icon: 'ri:user-line',
      iconColor: '#13DEB9',
      enabled: true,
      order: 2,
      routeName: 'Accounts'
    },
    {
      name: '在线聊天',
      description: '实时查看买家消息',
      icon: 'ri:message-3-line',
      iconColor: '#14b8a6',
      enabled: true,
      order: 3,
      routeName: 'OnlineChat'
    },
    {
      name: '订单管理',
      description: '订单同步与发货',
      icon: 'ri:shopping-bag-3-line',
      iconColor: '#ffb100',
      enabled: true,
      order: 4,
      routeName: 'Orders'
    },
    {
      name: '关键词回复',
      description: '自动回复规则',
      icon: 'ri:chat-smile-2-line',
      iconColor: '#7A7FFF',
      enabled: true,
      order: 5,
      routeName: 'Keywords'
    },
    {
      name: '系统设置',
      description: '基础配置与改密',
      icon: 'ri:settings-3-line',
      iconColor: '#ff6b6b',
      enabled: true,
      order: 6,
      routeName: 'XySettings'
    }
  ],
  quickLinks: [
    {
      name: '卡券管理',
      enabled: true,
      order: 1,
      routeName: 'Cards'
    },
    {
      name: '发货规则',
      enabled: true,
      order: 2,
      routeName: 'DeliveryRules'
    },
    {
      name: '手动补发',
      enabled: true,
      order: 3,
      routeName: 'ManualShip'
    },
    {
      name: '数据日志',
      enabled: true,
      order: 4,
      routeName: 'About'
    }
  ]
}

export default Object.freeze(fastEnterConfig)
