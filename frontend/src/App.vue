<script setup>
import { TooltipProvider } from 'reka-ui'
import { onBeforeUnmount, ref } from 'vue'
import { toast } from 'vue-sonner'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import AppToaster from '@/components/ui/AppToaster.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const serviceError = ref('')
const remaining = ref(0)
const retryKey = ref(0)
let timer
function retry() {
  clearInterval(timer)
  serviceError.value = ''
  retryKey.value += 1
}
function handleError(event) {
  const error = event.detail
  if (error.code === 'SERVICE_UNAVAILABLE') {
    serviceError.value = error.message
    if (remaining.value > 0) return
    remaining.value = 30
    timer = setInterval(() => {
      remaining.value -= 1
      if (remaining.value === 0) retry()
    }, 1000)
  } else if (['NETWORK_ERROR', 'INTERNAL_ERROR'].includes(error.code)) {
    // request_id는 서버 로그(Loki)에서 같은 요청을 찾는 번호
    const id = error.detail?.request_id
    toast.error(error.message, {
      ...(id && { description: `오류 번호 ${id}` }),
      action: { label: '화면 다시 불러오기', onClick: retry },
    })
  } else if (error.code === 'METHOD_NOT_ALLOWED') {
    toast.error(error.message)
  }
}
window.addEventListener('spacecube:api-error', handleError)
onBeforeUnmount(() => { window.removeEventListener('spacecube:api-error', handleError); clearInterval(timer) })
</script>

<template>
  <TooltipProvider :delay-duration="250">
    <a class="skip-link" href="#main">본문으로 건너뛰기</a>
    <AppHeader />
    <main id="main" tabindex="-1">
      <section v-if="serviceError" class="service-state container" role="alert">
        <h1>서비스 점검 중이에요</h1>
        <p>{{ serviceError }}</p>
        <p>{{ remaining }}초 뒤 화면을 다시 불러옵니다. 결제는 자동으로 재시도하지 않아요.</p>
        <BaseButton :disabled="remaining > 0" @click="retry">다시 시도</BaseButton>
      </section>
      <RouterView v-else :key="retryKey" />
    </main>
    <AppFooter />
    <AppToaster />
  </TooltipProvider>
</template>

<style scoped>
.service-state { padding-block: var(--sp-64); display: flex; flex-direction: column; align-items: flex-start; gap: var(--sp-16); }
.skip-link {
  position: absolute;
  left: var(--sp-16);
  top: -100px;
  z-index: 100;
  padding: var(--sp-12) var(--sp-16);
  border-radius: var(--r-md);
  background: var(--c-ink);
  color: var(--c-on-dark);
  font-weight: 700;
  text-decoration: none;
}
.skip-link:focus {
  top: var(--sp-8);
}
main {
  min-height: calc(100vh - var(--header-h));
}
main:focus {
  outline: none;
}
</style>
