<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NImage,
  NInput,
  NInputNumber,
  NSpace,
  NSwitch,
  NTag,
  NText,
  useMessage,
  type DataTableColumns
} from 'naive-ui'
import AccountTabs from '../components/AccountTabs.vue'
import { useAccountStore } from '../stores/account'
import {
  getYanghaoStatus,
  pauseYanghao,
  resumeYanghao,
  startYanghao,
  stopYanghao,
  type YanghaoRecord,
  type YanghaoStatus
} from '../api/yanghao'

const message = useMessage()
const accountStore = useAccountStore()
const busy = ref(false)
const status = ref<YanghaoStatus>({ status: 'idle', logs: [], records: [], today: { count: 0 } })

const form = ref({
  keyword: '',
  target_count: 50,
  dwell_sec: 10,
  leave_msg: true,
  message_text: '非常好，效果不错，很满意～',
  loop_times: 1
})

let timer: ReturnType<typeof setInterval> | null = null

const records = computed(() => status.value.records || [])

function statusTag(type: string, text: string) {
  const map: Record<string, 'success' | 'error' | 'warning' | 'default' | 'info'> = {
    ok: 'success',
    fail: 'error',
    pending: 'warning',
    skip: 'default'
  }
  return h(NTag, { size: 'small', type: map[type] || 'default', bordered: false }, () => text)
}

const columns: DataTableColumns<YanghaoRecord> = [
  {
    title: '序号',
    key: 'idx',
    width: 52,
    align: 'center',
    fixed: 'left',
    render: (_r, i) => i + 1
  },
  {
    title: '封面',
    key: 'pic',
    width: 64,
    align: 'center',
    fixed: 'left',
    render: (r) => {
      const src = String(r.pic_url || '')
      if (!src) return '-'
      return h(NImage, {
        src,
        width: 40,
        height: 40,
        objectFit: 'cover',
        lazy: true,
        style: 'border-radius:6px',
        fallbackSrc: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg"/>'
      })
    }
  },
  {
    title: '标题',
    key: 'title',
    ellipsis: { tooltip: true },
    width: 180,
    render: (r) =>
      h(
        'a',
        {
          href: r.web_url || (r.item_id ? `https://www.goofish.com/item?id=${r.item_id}` : '#'),
          target: '_blank',
          style: 'color: var(--n-primary-color)'
        },
        String(r.title || r.item_id || '-').slice(0, 40)
      )
  },
  {
    title: '现价',
    key: 'price',
    width: 72,
    align: 'center',
    render: (r) => h('span', { style: 'color:#18a058' }, String(r.price ?? '-'))
  },
  {
    title: '原价',
    key: 'original_price',
    width: 72,
    align: 'center',
    render: (r) =>
      h('span', { style: 'color:#f0a020;text-decoration:line-through' }, String(r.original_price ?? '-'))
  },
  {
    title: '想要',
    key: 'want_num',
    width: 56,
    align: 'center',
    render: (r) => r.want_num ?? '-'
  },
  {
    title: '浏览量',
    key: 'view_count',
    width: 64,
    align: 'center',
    render: (r) => r.view_count ?? '-'
  },
  {
    title: '卖家',
    key: 'seller_nick',
    width: 100,
    ellipsis: { tooltip: true },
    render: (r) => r.seller_nick || r.seller_id || '-'
  },
  {
    title: '浏览',
    key: 'browse_status',
    width: 78,
    align: 'center',
    render: (r) => {
      const s = String(r.browse_status || '')
      return statusTag(
        s,
        s === 'ok' ? '已浏览' : s === 'fail' ? '失败' : s === 'pending' ? '进行中' : s || '-'
      )
    }
  },
  {
    title: '留言',
    key: 'msg_status',
    width: 78,
    align: 'center',
    render: (r) => {
      const s = String(r.msg_status || '')
      return statusTag(
        s,
        s === 'ok' ? '成功' : s === 'fail' ? '失败' : s === 'skip' ? '跳过' : s === 'pending' ? '待发' : s || '-'
      )
    }
  },
  {
    title: '详情',
    key: 'msg_detail',
    ellipsis: { tooltip: true },
    width: 160,
    render: (r) => r.msg_detail || '-'
  },
  {
    title: '时间',
    key: 'ts',
    width: 72,
    align: 'center',
    render: (r) => r.ts || '-'
  }
]

async function refresh(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    status.value = { status: 'idle', logs: [], records: [], today: { count: 0 } }
    return
  }
  try {
    const res = await getYanghaoStatus(cid)
    status.value = res.data || { status: 'idle', logs: [], records: [] }
  } catch {
    /* ignore */
  }
}

async function onStart(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) {
    message.warning('请先选择账号')
    return
  }
  if (!form.value.keyword.trim()) {
    message.warning('请填写搜索关键词')
    return
  }
  busy.value = true
  try {
    const res = await startYanghao({
      cookie_id: cid,
      ...form.value,
      keyword: form.value.keyword.trim()
    })
    status.value = res.data || status.value
    message.success(res.message || '养号已开始')
  } catch (e: any) {
    message.error(e?.message || '启动失败')
  } finally {
    busy.value = false
    void refresh()
  }
}

async function onPause(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) return
  try {
    const res: any = await pauseYanghao(cid)
    status.value = res.data || status.value
    message.success('已暂停')
  } catch (e: any) {
    message.error(e?.message || '暂停失败')
  }
}

async function onResume(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) return
  try {
    const res: any = await resumeYanghao(cid, {
      keyword: form.value.keyword.trim(),
      target_count: form.value.target_count,
      dwell_sec: form.value.dwell_sec,
      loop_times: form.value.loop_times,
      leave_msg: form.value.leave_msg,
      message_text: form.value.message_text
    })
    status.value = res.data || status.value
    message.success(res.message || '已按当前最新设置继续')
  } catch (e: any) {
    message.error(e?.message || '继续失败')
  }
}

async function onStop(): Promise<void> {
  const cid = accountStore.activeCookieId
  if (!cid) return
  try {
    const res: any = await stopYanghao(cid)
    status.value = res.data || status.value
    message.success('已停止')
  } catch (e: any) {
    message.error(e?.message || '停止失败')
  }
}

watch(
  () => accountStore.activeCookieId,
  () => void refresh()
)

onMounted(() => {
  void refresh()
  timer = setInterval(() => void refresh(), 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <n-space vertical :size="14">
    <n-card title="养号助手" size="small">
      <AccountTabs />
      <n-text depth="3" style="display: block; margin: 8px 0 12px; font-size: 12px">
        按关键词搜索 → 逐个浏览并停留 → 可选真实私信留言（本质是站内私聊，需账号消息通道在线）。暂停后改浏览数/停留秒数/循环再点「继续」，会按最新设置生效。下方表格实时显示商品与留言结果。
      </n-text>

      <n-form label-placement="left" label-width="110" style="max-width: 720px">
        <n-form-item label="搜索关键词" required>
          <n-input
            v-model:value="form.keyword"
            clearable
            placeholder="例：软件开发、设计素材、虚拟资料（需自己填写）"
          />
        </n-form-item>
        <n-form-item label="浏览数量">
          <n-input-number v-model:value="form.target_count" :min="1" :max="500" style="width: 160px" />
        </n-form-item>
        <n-form-item label="停留秒数">
          <n-input-number v-model:value="form.dwell_sec" :min="1" :max="120" style="width: 160px" />
        </n-form-item>
        <n-form-item label="循环轮次">
          <n-input-number v-model:value="form.loop_times" :min="1" :max="20" style="width: 160px" />
        </n-form-item>
        <n-form-item label="自动留言">
          <n-space align="center">
            <n-switch v-model:value="form.leave_msg" />
            <n-text depth="3" style="font-size: 12px">开启后会真实给卖家发私信（失败会在表格标注）</n-text>
          </n-space>
        </n-form-item>
        <n-form-item v-if="form.leave_msg" label="留言内容">
          <n-input
            v-model:value="form.message_text"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="给对方商品留言/私信的内容"
          />
        </n-form-item>
      </n-form>

      <n-space style="margin-bottom: 12px">
        <n-button
          type="primary"
          :loading="busy"
          :disabled="status.status === 'running' || status.status === 'paused'"
          @click="onStart"
        >
          开始养号
        </n-button>
        <n-button secondary :disabled="status.status !== 'running'" @click="onPause">暂停</n-button>
        <n-button secondary :disabled="status.status !== 'paused'" @click="onResume">继续</n-button>
        <n-button
          type="error"
          secondary
          :disabled="status.status === 'idle' || status.status === 'done' || status.status === 'stopped'"
          @click="onStop"
        >
          停止
        </n-button>
        <n-button quaternary @click="refresh">刷新状态</n-button>
      </n-space>

      <n-space align="center" :size="10" style="margin-bottom: 8px" wrap>
        <n-tag size="small" :type="status.status === 'running' ? 'success' : 'default'">
          状态：{{ status.status || 'idle' }}
        </n-tag>
        <n-text depth="3">进度 {{ status.progress || `${status.browsed || 0}/${form.target_count}` }}</n-text>
        <n-text depth="3">已浏览 {{ status.browsed || 0 }}</n-text>
        <n-text depth="3">浏览失败 {{ status.browse_failed || 0 }}</n-text>
        <n-text depth="3">留言成功 {{ status.messaged || 0 }}</n-text>
        <n-text depth="3">留言失败 {{ status.msg_failed || 0 }}</n-text>
        <n-text depth="3">今日养号 {{ status.today?.count || 0 }} 次</n-text>
      </n-space>
    </n-card>

    <n-card title="养号商品明细" size="small">
      <div style="width: 100%; overflow: auto">
        <n-data-table
          :columns="columns"
          :data="records"
          size="small"
          :bordered="true"
          :single-line="false"
          :scroll-x="1100"
          :max-height="440"
          :row-key="(r) => `${r.item_id || 'x'}-${r.ts || ''}-${r.round || 0}-${r.title || ''}`"
        />
      </div>
      <n-text v-if="!records.length" depth="3" style="display: block; margin-top: 8px; font-size: 12px">
        开始养号后，这里会像采集页一样逐条实时显示缩略图、标题、价格、浏览/留言结果
      </n-text>
    </n-card>

    <n-card title="运行日志" size="small">
      <div
        style="
          max-height: 220px;
          overflow: auto;
          font-family: ui-monospace, Consolas, monospace;
          font-size: 12px;
          line-height: 1.6;
          white-space: pre-wrap;
        "
      >
        <div v-for="(line, i) in status.logs || []" :key="i">{{ line }}</div>
        <n-text v-if="!(status.logs || []).length" depth="3">暂无日志</n-text>
      </div>
    </n-card>
  </n-space>
</template>
