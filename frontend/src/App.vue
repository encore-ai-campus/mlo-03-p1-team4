<script setup>
import { TooltipProvider } from 'reka-ui'
import { onBeforeUnmount, ref } from 'vue'
import { toast } from 'vue-sonner'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import AppToaster from '@/components/ui/AppToaster.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

// 화면 전환은 첫 화면이 그려진 뒤의 이동에만 쓴다(처음 연 화면은 바로 보이게).
const pageTransition = ref('none')
const router = useRouter()
router?.isReady?.().then(() => setTimeout(() => (pageTransition.value = 'page'), 0))

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
      <!-- 화면 전환: 경로가 바뀔 때만 짧게 페이드(같은 화면의 검색 조건 변경은 전환하지 않음) -->
      <RouterView v-else v-slot="{ Component, route }">
        <!-- 화면 컴포넌트는 최상위 요소가 여럿일 수 있어 감싸는 div 하나에만 전환을 준다 -->
        <Transition :name="pageTransition" mode="out-in">
          <div :key="`${route.path}#${retryKey}`" class="page-view">
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>
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

<style>
/* 화면 전환(11-07 팀 피드백): 나갈 때 빠르게 흐려지고 새 화면이 부드럽게 나타난다.
   위치는 움직이지 않는다(버튼이 움직이는 동안 누르기 어렵지 않게). 움직임 줄이기 설정이면 끈다. */
.page-enter-active {
  transition: opacity var(--t-base) var(--ease-out);
}
.page-leave-active {
  transition: opacity var(--t-fast) var(--ease-out);
}
.page-enter-from,
.page-leave-to {
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active {
    transition: none;
  }
}
</style>
