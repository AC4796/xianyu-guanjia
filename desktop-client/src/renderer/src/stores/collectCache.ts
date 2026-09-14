import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useCollectCacheStore = defineStore('collectCache', () => {
  const keyword = ref('')
  const page = ref(1)
  const pageSize = ref(30)
  const total = ref(0)
  /** 一次采集到的全部数据，翻页只切本地切片 */
  const allRows = ref<any[]>([])
  const minWant = ref<number | null>(null)
  const minView = ref<number | null>(null)
  const fetchCount = ref(100)

  const rows = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return allRows.value.slice(start, start + pageSize.value)
  })

  function setResult(payload: {
    keyword: string
    page?: number
    total: number
    rows: any[]
    pageSize?: number
    minWant?: number | null
    minView?: number | null
    fetchCount?: number
  }) {
    keyword.value = payload.keyword
    page.value = payload.page ?? 1
    total.value = payload.total
    allRows.value = payload.rows || []
    if (payload.pageSize != null) pageSize.value = payload.pageSize
    if (payload.minWant !== undefined) minWant.value = payload.minWant
    if (payload.minView !== undefined) minView.value = payload.minView
    if (payload.fetchCount != null) fetchCount.value = payload.fetchCount
  }

  function clear() {
    keyword.value = ''
    page.value = 1
    pageSize.value = 30
    total.value = 0
    allRows.value = []
    minWant.value = null
    minView.value = null
  }

  return {
    keyword,
    page,
    pageSize,
    total,
    allRows,
    rows,
    minWant,
    minView,
    fetchCount,
    setResult,
    clear
  }
})
