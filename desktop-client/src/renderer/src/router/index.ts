import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true }
    },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'home', component: () => import('../views/HomeView.vue') },
        { path: 'messages', name: 'messages', component: () => import('../views/MessagesView.vue') },
        { path: 'orders', name: 'orders', component: () => import('../views/OrdersView.vue') },
        {
          path: 'cards-inventory',
          name: 'cards-inventory',
          component: () => import('../views/CardsInventoryView.vue')
        },
        {
          path: 'ship-templates',
          name: 'ship-templates',
          component: () => import('../views/ShipTemplatesView.vue')
        },
        { path: 'items', name: 'items', component: () => import('../views/ItemsView.vue') },
        { path: 'collect', name: 'collect', component: () => import('../views/CollectView.vue') },
        {
          path: 'seller-watch',
          name: 'seller-watch',
          component: () => import('../views/SellerWatchView.vue')
        },
        {
          path: 'publish',
          name: 'publish',
          component: () => import('../views/PublishView.vue')
        },
        {
          path: 'favorites',
          name: 'favorites',
          component: () => import('../views/FavoritesView.vue')
        },
        {
          path: 'yanghao',
          name: 'yanghao',
          component: () => import('../views/YanghaoView.vue')
        },
        {
          path: 'sensitive-words',
          name: 'sensitive-words',
          component: () => import('../views/SensitiveWordsView.vue')
        },
        {
          path: 'keyword-reply',
          name: 'keyword-reply',
          component: () => import('../views/KeywordReplyView.vue')
        },
        {
          path: 'item-reply',
          name: 'item-reply',
          component: () => import('../views/ItemReplyView.vue')
        },
        {
          path: 'notify-settings',
          name: 'notify-settings',
          component: () => import('../views/NotifySettingsView.vue')
        },
        { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue') }
      ]
    }
  ]
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (auth.loading) {
    await auth.refresh()
  }

  if (to.meta.public) return true

  const entered = sessionStorage.getItem('xy_entered_workbench') === '1'
  if (!entered) return { name: 'login' }
  if (!auth.authenticated) return { name: 'login' }
  return true
})

export default router
