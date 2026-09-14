/** 按账号本地收藏（localStorage） */

export interface FavoriteItem {
  item_id: string
  title: string
  price: string | number
  main_image: string
  item_url: string
  seller_name: string
  saved_at: string
  /** 上次在线检测结果：online | offline | unknown */
  status?: 'unknown' | 'online' | 'offline'
}

function storageKey(cookieId: string): string {
  return `xy_favorites_${cookieId || 'default'}`
}

export function loadFavorites(cookieId: string): FavoriteItem[] {
  try {
    const raw = localStorage.getItem(storageKey(cookieId))
    const list = JSON.parse(raw || '[]')
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export function saveFavorites(cookieId: string, list: FavoriteItem[]): void {
  localStorage.setItem(storageKey(cookieId), JSON.stringify(list))
}

export function upsertFavorite(cookieId: string, item: FavoriteItem): FavoriteItem[] {
  const list = loadFavorites(cookieId)
  const id = String(item.item_id || '')
  const idx = list.findIndex((x) => String(x.item_id) === id)
  if (idx >= 0) list.splice(idx, 1)
  list.unshift(item)
  saveFavorites(cookieId, list)
  return list
}

export function removeFavorite(cookieId: string, itemId: string): FavoriteItem[] {
  const list = loadFavorites(cookieId).filter((x) => String(x.item_id) !== String(itemId))
  saveFavorites(cookieId, list)
  return list
}

export function isFavorite(cookieId: string, itemId: string): boolean {
  return loadFavorites(cookieId).some((x) => String(x.item_id) === String(itemId))
}

export function toggleFavoriteFromRow(cookieId: string, row: any): { added: boolean; list: FavoriteItem[] } {
  const id = String(row.item_id || row.id || '')
  if (!id || !cookieId) return { added: false, list: loadFavorites(cookieId) }
  if (isFavorite(cookieId, id)) {
    return { added: false, list: removeFavorite(cookieId, id) }
  }
  const item: FavoriteItem = {
    item_id: id,
    title: String(row.title || row.item_title || ''),
    price: (row.price ?? row.item_price ?? '') as string | number,
    main_image: String(row.main_image || row.pic_url || row.image || row.pictUrl || ''),
    item_url: String(row.item_url || `https://www.goofish.com/item?id=${id}`),
    seller_name: String(row.seller_name || row.seller || row.nick || ''),
    saved_at: new Date().toISOString()
  }
  return { added: true, list: upsertFavorite(cookieId, item) }
}
