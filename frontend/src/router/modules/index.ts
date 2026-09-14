import { AppRouteRecord } from '@/types/router'
import { dashboardRoutes } from './dashboard'
import { xianyuRoutes } from './xianyu'

/**
 * 导出所有模块化路由（异常页走静态路由，不进侧栏）
 */
export const routeModules: AppRouteRecord[] = [dashboardRoutes, ...xianyuRoutes]
