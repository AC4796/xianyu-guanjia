import { AppRouteRecord } from '@/types/router'

const roles = ['R_SUPER', 'R_ADMIN', 'R_USER']
const adminRoles = ['R_SUPER', 'R_ADMIN']

export const xianyuRoutes: AppRouteRecord[] = [
  {
    path: '/accounts',
    name: 'AccountsRoot',
    component: '/index/index',
    meta: { title: '账号管理', icon: 'ri:user-line', roles },
    children: [
      {
        path: '',
        name: 'Accounts',
        component: '/xianyu/accounts',
        meta: { title: '闲鱼账号', keepAlive: true, roles }
      }
    ]
  },
  {
    path: '/trade',
    name: 'Trade',
    component: '/index/index',
    meta: { title: '交易中心', icon: 'ri:shopping-bag-3-line', roles },
    children: [
      {
        path: 'orders',
        name: 'Orders',
        component: '/xianyu/orders',
        meta: { title: '订单管理', keepAlive: true, roles }
      },
      {
        path: 'items',
        name: 'Items',
        component: '/xianyu/items',
        meta: { title: '商品管理', keepAlive: true, roles }
      },
      {
        path: 'manual-ship',
        name: 'ManualShip',
        component: '/xianyu/manual-ship',
        meta: { title: '手动补发', keepAlive: true, roles }
      },
      {
        path: 'item-search',
        name: 'ItemSearch',
        component: '/xianyu/item-search',
        meta: { title: '商品搜索', keepAlive: false, roles }
      }
    ]
  },
  {
    path: '/auto-reply',
    name: 'AutoReply',
    component: '/index/index',
    meta: { title: '自动回复', icon: 'ri:chat-smile-2-line', roles },
    children: [
      {
        path: 'keywords',
        name: 'Keywords',
        component: '/xianyu/keywords',
        meta: { title: '关键词回复', keepAlive: true, roles }
      },
      {
        path: 'item-replies',
        name: 'ItemReplies',
        component: '/xianyu/item-replies',
        meta: { title: '商品回复', keepAlive: true, roles }
      }
    ]
  },
  {
    path: '/delivery',
    name: 'DeliveryRoot',
    component: '/index/index',
    meta: { title: '发货管理', icon: 'ri:truck-line', roles },
    children: [
      {
        path: 'cards',
        name: 'Cards',
        component: '/xianyu/cards',
        meta: { title: '卡券管理', keepAlive: true, roles }
      },
      {
        path: 'rules',
        name: 'DeliveryRules',
        component: '/xianyu/delivery',
        meta: { title: '发货规则', keepAlive: true, roles }
      }
    ]
  },
  {
    path: '/notify',
    name: 'Notify',
    component: '/index/index',
    meta: { title: '消息通知', icon: 'ri:notification-3-line', roles },
    children: [
      {
        path: 'online-chat',
        name: 'OnlineChat',
        component: '/xianyu/online-chat',
        meta: { title: '在线聊天', keepAlive: true, roles }
      },
      {
        path: 'channels',
        name: 'NotificationChannels',
        component: '/xianyu/notification-channels',
        meta: { title: '通知渠道', keepAlive: true, roles }
      },
      {
        path: 'messages',
        name: 'MessageNotifications',
        component: '/xianyu/message-notifications',
        meta: { title: '账号通知', keepAlive: true, roles }
      }
    ]
  },
  {
    path: '/system-xy',
    name: 'SystemXy',
    component: '/index/index',
    meta: { title: '系统', icon: 'ri:settings-3-line', roles },
    children: [
      {
        path: 'settings',
        name: 'XySettings',
        component: '/xianyu/settings',
        meta: { title: '系统设置', keepAlive: true, roles }
      },
      {
        path: 'about',
        name: 'About',
        component: '/xianyu/about',
        meta: { title: '数据日志', keepAlive: true, roles }
      },
      {
        path: 'disclaimer',
        name: 'Disclaimer',
        component: '/xianyu/disclaimer',
        meta: { title: '免责声明', keepAlive: false, roles }
      }
    ]
  },
  {
    path: '/admin-xy',
    name: 'AdminXy',
    component: '/index/index',
    meta: { title: '管理后台', icon: 'ri:shield-user-line', roles: adminRoles },
    children: [
      {
        path: 'users',
        name: 'AdminUsers',
        component: '/xianyu/admin/users',
        meta: { title: '用户管理', keepAlive: true, roles: adminRoles }
      },
      {
        path: 'logs',
        name: 'AdminLogs',
        component: '/xianyu/admin/logs',
        meta: { title: '系统日志', keepAlive: true, roles: adminRoles }
      },
      {
        path: 'risk-logs',
        name: 'AdminRiskLogs',
        component: '/xianyu/admin/risk-logs',
        meta: { title: '风控日志', keepAlive: true, roles: adminRoles }
      },
      {
        path: 'data',
        name: 'AdminData',
        component: '/xianyu/admin/data',
        meta: { title: '数据管理', keepAlive: true, roles: adminRoles }
      }
    ]
  }
]
