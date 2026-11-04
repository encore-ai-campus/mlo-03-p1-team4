<script setup>
import { useId } from 'vue'

// 라벨이 늘 보이는 입력칸. 오류는 칸 바로 아래에 보여 주고 화면 읽기 프로그램에도 연결한다.
// multiline이면 textarea. 그 밖의 속성(type, autocomplete, inputmode 등)은 그대로 input에 붙는다.
defineOptions({ inheritAttrs: false })
defineProps({
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  multiline: { type: Boolean, default: false },
  optional: { type: Boolean, default: false },
})
const model = defineModel({ type: String, default: '' })
const id = useId()
</script>

<template>
  <div class="input-field" :class="{ 'has-error': error }">
    <label :for="id" class="input-field__label">{{ label }}<span v-if="optional" class="input-field__opt"> (선택)</span></label>
    <div class="input-field__row">
      <textarea v-if="multiline" :id="id" v-model="model" v-bind="$attrs" class="input-field__control is-multi" :aria-invalid="Boolean(error)" :aria-describedby="error ? `${id}-err` : hint ? `${id}-hint` : undefined" />
      <input v-else :id="id" v-model="model" v-bind="$attrs" class="input-field__control" :aria-invalid="Boolean(error)" :aria-describedby="error ? `${id}-err` : hint ? `${id}-hint` : undefined" />
      <slot name="append" />
    </div>
    <p v-if="error" :id="`${id}-err`" class="input-field__error" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-hint`" class="input-field__hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.input-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.input-field__label {
  font-size: var(--fs-13);
  font-weight: 700;
  color: var(--c-muted);
}
.input-field__opt {
  font-weight: 400;
}
.input-field__row {
  display: flex;
  gap: var(--sp-8);
}
.input-field__control {
  flex: 1;
  min-width: 0;
  min-height: 48px;
  padding: 0 var(--sp-12);
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-md);
  background: var(--c-surface);
  font-size: var(--fs-16);
  transition: border-color var(--t-fast), box-shadow var(--t-fast);
}
.input-field__control.is-multi {
  min-height: 112px;
  padding: var(--sp-12);
  resize: vertical;
  line-height: 1.6;
}
.input-field__control:focus {
  border-color: var(--c-brand);
  outline: none;
  box-shadow: 0 0 0 3px var(--c-brand-ring);
}
.has-error .input-field__control {
  border-color: var(--c-danger);
}
.input-field__error {
  font-size: var(--fs-13);
  color: var(--c-danger);
}
.input-field__hint {
  font-size: var(--fs-13);
  color: var(--c-subtle);
}
</style>
