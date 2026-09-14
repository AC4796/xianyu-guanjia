<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  NForm,
  NFormItem,
  NInputNumber,
  NModal,
  NRadio,
  NRadioGroup,
  NSpace,
  NSwitch,
  NText,
  NButton
} from 'naive-ui'
import {
  defaultShelfOptions,
  loadShelfOptions,
  saveShelfOptions,
  type ShelfOptions
} from '../utils/shelfOptions'

const props = defineProps<{
  show: boolean
  title?: string
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'confirm', opts: ShelfOptions): void
}>()

const form = ref<ShelfOptions>(loadShelfOptions())

watch(
  () => props.show,
  (v) => {
    if (v) form.value = loadShelfOptions()
  }
)

function onCancel(): void {
  emit('update:show', false)
}

function onOk(): void {
  saveShelfOptions(form.value)
  emit('confirm', { ...form.value })
  emit('update:show', false)
}

function onReset(): void {
  form.value = defaultShelfOptions()
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="title || '上架设置'"
    style="width: 480px"
    @update:show="(v) => emit('update:show', v)"
  >
    <n-form label-placement="left" label-width="110">
      <n-form-item label="加价上架">
        <n-space align="center">
          <n-switch v-model:value="form.markupEnabled" />
          <n-text depth="3" style="font-size: 12px">关闭则按对方原价上架</n-text>
        </n-space>
      </n-form-item>
      <n-form-item v-if="form.markupEnabled" label="加价方式">
        <n-space align="center">
          <n-radio-group v-model:value="form.markupType" name="shelf-markup">
            <n-radio value="percent">比例 %</n-radio>
            <n-radio value="amount">金额 ¥</n-radio>
          </n-radio-group>
          <n-input-number v-model:value="form.markupValue" :min="0" :precision="2" style="width: 120px" />
        </n-space>
      </n-form-item>
      <n-form-item label="文字去重">
        <n-space vertical>
          <n-switch v-model:value="form.dedupText" />
          <n-text depth="3" style="font-size: 12px">
            仅改写标题/描述（标题仍强制 ≤30 字）。图片始终上传原图，不做裁剪模糊。
          </n-text>
        </n-space>
      </n-form-item>
    </n-form>
    <n-space justify="space-between" style="margin-top: 8px">
      <n-button quaternary @click="onReset">恢复默认</n-button>
      <n-space>
        <n-button @click="onCancel">取消</n-button>
        <n-button type="primary" @click="onOk">确认上架</n-button>
      </n-space>
    </n-space>
  </n-modal>
</template>
