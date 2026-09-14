<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NRadioButton,
  NRadioGroup,
  NSpace,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  NText,
  useMessage,
  type DataTableColumns
} from 'naive-ui'
import {
  detectSensitive,
  listSensitivePlatforms,
  reloadSensitiveLexicon,
  rewriteSensitive,
  type SensitiveHit,
  type SensitivePlatform
} from '../api/sensitive'

const message = useMessage()
const platforms = ref<SensitivePlatform[]>([])
const platform = ref('goofish')
const title = ref('')
const desc = ref('')
const mode = ref<'mask' | 'replace' | 'smart'>('smart')
const deep = ref(true)
const busy = ref(false)
const detectResult = ref<any>(null)
const rewriteResult = ref<any>(null)

const readyPlatforms = computed(() => platforms.value.filter((p) => p.ready))
const comingPlatforms = computed(() => platforms.value.filter((p) => !p.ready))

const levelType = (lv?: string) => {
  if (lv === 'block') return 'error'
  if (lv === 'warn') return 'warning'
  if (lv === 'pass' || lv === 'ok') return 'success'
  return 'default'
}

const hitColumns: DataTableColumns<SensitiveHit> = [
  { title: '敏感词', key: 'word', width: 140, ellipsis: { tooltip: true } },
  {
    title: '级别',
    key: 'level',
    width: 80,
    align: 'center',
    render: (r) =>
      h(
        NTag,
        { size: 'small', type: levelType(r.level) as any, bordered: false },
        () => r.level || '-'
      )
  },
  { title: '分类', key: 'category', width: 90 },
  { title: '上下文', key: 'snippet', ellipsis: { tooltip: true } }
]

async function loadPlatforms() {
  try {
    const res = await listSensitivePlatforms()
    platforms.value = res.data || [
      { id: 'goofish', name: '闲鱼', ready: true },
      { id: 'taobao', name: '淘宝', ready: false },
      { id: 'pinduoduo', name: '拼多多', ready: false },
      { id: 'douyin', name: '抖音电商', ready: false }
    ]
  } catch {
    platforms.value = [
      { id: 'goofish', name: '闲鱼', ready: true },
      { id: 'taobao', name: '淘宝', ready: false },
      { id: 'pinduoduo', name: '拼多多', ready: false },
      { id: 'douyin', name: '抖音电商', ready: false }
    ]
  }
}

function combinedText() {
  const parts = [title.value.trim(), desc.value.trim()].filter(Boolean)
  return parts.join('\n')
}

async function onDetect() {
  const text = combinedText()
  if (!text) {
    message.warning('请填写标题或描述')
    return
  }
  busy.value = true
  rewriteResult.value = null
  try {
    const res = await detectSensitive({
      platform: platform.value,
      text,
      title: title.value,
      desc: desc.value
    })
    detectResult.value = res.data
    const hits = res.data?.hit_count || 0
    if (hits > 0) message.warning(`检测到 ${hits} 处敏感内容（词库 ${res.data?.word_count || 0} 条）`)
    else message.success('未发现敏感词')
  } catch (e: any) {
    message.error(e?.message || '检测失败')
  } finally {
    busy.value = false
  }
}

async function onRewrite() {
  const text = combinedText()
  if (!text) {
    message.warning('请填写标题或描述')
    return
  }
  busy.value = true
  try {
    const res = await rewriteSensitive({
      platform: platform.value,
      text,
      mode: mode.value,
      deep: deep.value
    })
    rewriteResult.value = res.data
    detectResult.value = res.data?.final_detect || res.data?.detect || detectResult.value
    if (res.data?.clean) message.success(`重绘完成：已净化（${res.data.rounds || 1} 轮，替换 ${res.data.replacements?.length || 0} 处）`)
    else message.warning(`已重绘但仍有 ${res.data?.remaining_hits || 0} 处残留，可再点一次或改用星号遮罩`)
  } catch (e: any) {
    message.error(e?.message || '改写失败')
  } finally {
    busy.value = false
  }
}

function applyRewritten() {
  const t = rewriteResult.value?.rewritten
  if (!t) return
  if (title.value && !desc.value) title.value = t
  else desc.value = t
  message.success('已填回编辑框，可再微调后复检')
}

async function onReload() {
  try {
    const res = await reloadSensitiveLexicon(platform.value)
    message.success(
      `词库已重载：${res.data?.word_count || 0} 条（扩展 ${res.data?.extra_loaded || 0}）`
    )
  } catch (e: any) {
    message.error(e?.message || '重载失败')
  }
}

onMounted(() => void loadPlatforms())
</script>

<template>
  <n-space vertical :size="14">
    <n-card title="敏感词检测" size="small">
      <n-text depth="3" style="display: block; margin-bottom: 12px; font-size: 12px">
        本地 DFA 引擎（参考 ToolGood.Words / Sensitive-lexicon /
        sensitive_content_filter）：闲鱼核心词库 + GitHub 开源扩展词库 + 灰产/导流短语规则。支持智能多轮重绘，直到检测通过。
      </n-text>

      <n-tabs v-model:value="platform" type="line" animated>
        <n-tab-pane v-for="p in readyPlatforms" :key="p.id" :name="p.id" :tab="p.name" />
        <n-tab-pane
          v-for="p in comingPlatforms"
          :key="p.id"
          :name="p.id"
          :tab="`${p.name}（即将支持）`"
          disabled
        />
      </n-tabs>

      <n-alert v-if="platform !== 'goofish'" type="info" style="margin: 8px 0 12px">
        当前仅开放闲鱼词库，其它平台敬请期待。
      </n-alert>

      <n-form label-placement="left" label-width="90" style="margin-top: 8px">
        <n-form-item label="商品标题">
          <n-input v-model:value="title" clearable placeholder="粘贴要检测的标题" maxlength="60" show-count />
        </n-form-item>
        <n-form-item label="商品描述">
          <n-input
            v-model:value="desc"
            type="textarea"
            :autosize="{ minRows: 5, maxRows: 14 }"
            placeholder="粘贴要检测的描述文案"
          />
        </n-form-item>
        <n-form-item label="重绘模式">
          <n-radio-group v-model:value="mode">
            <n-radio-button value="smart">智能重绘</n-radio-button>
            <n-radio-button value="replace">词表替换</n-radio-button>
            <n-radio-button value="mask">星号遮罩</n-radio-button>
          </n-radio-group>
        </n-form-item>
        <n-form-item label="深度多轮">
          <n-space align="center">
            <n-switch v-model:value="deep" />
            <n-text depth="3" style="font-size: 12px">开启后会反复检测+替换，尽量直到无敏感词</n-text>
          </n-space>
        </n-form-item>
      </n-form>

      <n-space>
        <n-button type="primary" :loading="busy" @click="onDetect">开始检测</n-button>
        <n-button type="info" secondary :loading="busy" @click="onRewrite">词语重绘</n-button>
        <n-button quaternary @click="onReload">重载词库</n-button>
      </n-space>
    </n-card>

    <n-card v-if="detectResult" title="检测结果" size="small">
      <n-space align="center" style="margin-bottom: 10px" wrap>
        <n-tag :type="levelType(detectResult.level)" size="small">
          级别：{{ detectResult.level || '-' }}
        </n-tag>
        <n-text>命中 {{ detectResult.hit_count || 0 }} 处</n-text>
        <n-text depth="3">词库 {{ detectResult.word_count || 0 }} 条</n-text>
        <n-text v-if="detectResult.extra_loaded" depth="3">扩展 {{ detectResult.extra_loaded }}</n-text>
        <n-text v-if="(detectResult.categories || []).length" depth="3">
          分类：{{ (detectResult.categories || []).join('、') }}
        </n-text>
      </n-space>
      <n-data-table
        :columns="hitColumns"
        :data="detectResult.hits || []"
        size="small"
        :bordered="false"
        :max-height="280"
      />
    </n-card>

    <n-card v-if="rewriteResult" title="重绘结果" size="small">
      <n-space align="center" style="margin-bottom: 10px" wrap>
        <n-tag :type="rewriteResult.clean ? 'success' : 'warning'" size="small">
          {{ rewriteResult.clean ? '已净化通过' : `仍有残留 ${rewriteResult.remaining_hits || 0} 处` }}
        </n-tag>
        <n-text depth="3">轮次 {{ rewriteResult.rounds || 1 }}</n-text>
        <n-text depth="3">替换 {{ (rewriteResult.replacements || []).length }} 处</n-text>
        <n-text depth="3">模式 {{ rewriteResult.mode }}{{ rewriteResult.deep ? ' · deep' : '' }}</n-text>
      </n-space>

      <n-space vertical :size="10">
        <div>
          <n-text depth="3" style="font-size: 12px">原文</n-text>
          <div
            style="
              margin-top: 4px;
              padding: 10px;
              background: rgba(128, 128, 128, 0.08);
              border-radius: 8px;
              white-space: pre-wrap;
              line-height: 1.6;
            "
          >
            {{ rewriteResult.original }}
          </div>
        </div>
        <div>
          <n-text depth="3" style="font-size: 12px">重绘后</n-text>
          <div
            style="
              margin-top: 4px;
              padding: 10px;
              background: rgba(24, 160, 88, 0.08);
              border-radius: 8px;
              white-space: pre-wrap;
              line-height: 1.6;
            "
          >
            {{ rewriteResult.rewritten }}
          </div>
        </div>

        <n-card
          v-if="rewriteResult.final_detect && !rewriteResult.clean"
          size="small"
          title="二次检测残留"
          :bordered="false"
          style="background: rgba(208, 48, 80, 0.04)"
        >
          <n-data-table
            :columns="hitColumns"
            :data="rewriteResult.final_detect.hits || []"
            size="small"
            :bordered="false"
            :max-height="180"
          />
        </n-card>

        <n-space>
          <n-button size="small" type="primary" secondary @click="applyRewritten">填回编辑框</n-button>
          <n-button size="small" secondary :loading="busy" @click="onRewrite">再重绘一轮</n-button>
        </n-space>
      </n-space>
    </n-card>
  </n-space>
</template>
