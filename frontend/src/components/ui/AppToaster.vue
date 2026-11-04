<script setup>
import { computed } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { Toaster } from 'vue-sonner'
// 토스트는 어디서든 `import { toast } from 'vue-sonner'` 후 toast.success('...')로 띄운다.
// 4초 뒤 사라지고, 오류(toast.error)는 스크린리더가 바로 읽는다. 색은 base.css에서 토큰으로 덮는다.
// 폰에서는 상세·조회의 하단 고정 바를 가리지 않도록 화면 위쪽에 띄운다.
const isPhone = useMediaQuery('(max-width: 767px)')
const position = computed(() => (isPhone.value ? 'top-center' : 'bottom-center'))
</script>

<template>
  <Toaster :position="position" :duration="4000" rich-colors close-button :toast-options="{ style: { fontFamily: 'var(--font-sans)' } }" />
</template>
