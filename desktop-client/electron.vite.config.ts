import { resolve } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import vue from '@vitejs/plugin-vue'

const API_TARGET = 'http://127.0.0.1:8080'
const proxyPaths = [
  '/login',
  '/logout',
  '/verify',
  '/generate-captcha',
  '/verify-captcha',
  '/system-settings',
  '/automation-settings',
  '/ai-reply-settings',
  '/ai-reply-test',
  '/cookies',
  '/cookie',
  '/api',
  '/keywords',
  '/keywords-with-item-id',
  '/keywords-with-type',
  '/keywords-export',
  '/keywords-import',
  '/items',
  '/cards',
  '/orders',
  '/item-replies',
  '/item-reply',
  '/itemReplays',
  '/upload-image',
  '/static',
  '/chat',
  '/admin',
  '/message-notifications',
  '/notification-channels',
  '/delivery-rules',
  '/default-reply',
  '/default-replies',
  '/user-settings',
  '/analytics',
  '/qr-login',
  '/password-login',
  '/backup',
  '/change-password',
  '/change-admin-password',
  '/ws',
  '/seller-watch',
  '/dropship-jobs',
  '/yanghao',
  '/sensitive',
  '/health'
]

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()]
  },
  preload: {
    plugins: [externalizeDepsPlugin()]
  },
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src')
      }
    },
    plugins: [vue()],
    server: {
      proxy: Object.fromEntries(
        proxyPaths.map((p) => [
          p,
          {
            target: API_TARGET,
            changeOrigin: true,
            ws: p === '/ws'
          }
        ])
      )
    }
  }
})
