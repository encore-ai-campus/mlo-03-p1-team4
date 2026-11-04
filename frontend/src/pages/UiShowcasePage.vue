<script setup>
import { ref } from 'vue'
import { toast } from 'vue-sonner'
import { Filter, Info, MoreHorizontal } from '@lucide/vue'
import SidebarLayout from '@/components/layout/SidebarLayout.vue'
import SplitLayout from '@/components/layout/SplitLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiAccordion from '@/components/ui/UiAccordion.vue'
import UiDialog from '@/components/ui/UiDialog.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiMenu from '@/components/ui/UiMenu.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
import UiTooltip from '@/components/ui/UiTooltip.vue'

// 다른 화면을 만들 때 공통 컴포넌트가 어떻게 생겼는지 보는 곳 (/ui). 실제 서비스 메뉴에는 없다.
const cancelOpen = ref(false)
const filterOpen = ref(false)
const saving = ref(false)
const whiteboard = ref(true)
const parking = ref(false)
const people = ref('4')
const faq = [
  { value: 'guide', title: '이용 안내', body: '예약은 1시간 단위, 최소 1시간부터 가능해요. 입실은 시작 10분 전부터 할 수 있어요.' },
  { value: 'refund', title: '환불 규정', body: '[취소 가능 기한과 환불 비율은 팀 결정 후 채움]' },
]

function fakeSave() {
  saving.value = true
  setTimeout(() => {
    saving.value = false
    toast.success('결제가 완료되어 예약이 확정됐어요')
  }, 1200)
}
function cancelReservation() {
  cancelOpen.value = false
  toast('예약을 취소했어요. 결제 금액은 모의 환불돼요.')
}
</script>

<template>
  <div class="container showcase">
    <h1 class="title">컴포넌트 모음</h1>
    <p class="lead">공통 레이아웃과 컴포넌트를 한곳에서 확인하는 개발용 페이지예요.</p>

    <section class="block">
      <h2>버튼 · 칩 · 토스트</h2>
      <div class="row">
        <BaseButton :loading="saving" @click="fakeSave">20,000원 결제하고 확정</BaseButton>
        <BaseButton variant="secondary" @click="toast.error('13:00 칸은 방금 다른 회원이 먼저 신청했어요. 다른 시간을 골라 주세요.')">칸 충돌 토스트</BaseButton>
        <BaseButton variant="quiet">조용한 버튼</BaseButton>
        <UiChip v-model="whiteboard">화이트보드</UiChip>
        <UiChip v-model="parking">주차 가능</UiChip>
      </div>
    </section>

    <section class="block">
      <h2>드롭다운 · 메뉴 · 툴팁</h2>
      <div class="row">
        <UiSelect v-model="people" label="인원" :options="['1', '2', '4', '6', '8'].map((n) => ({ value: n, label: `${n}명` }))" class="w160" />
        <UiMenu :items="[{ label: '예약 내역', onSelect: () => toast('예약 내역으로 이동') }, { label: '로그아웃', onSelect: () => toast('로그아웃했어요') }]">
          <BaseButton variant="secondary" aria-label="더 보기"><MoreHorizontal :size="18" aria-hidden="true" />메뉴</BaseButton>
        </UiMenu>
        <UiTooltip text="화이트보드 (가로 3m)">
          <button type="button" class="icon-btn" aria-label="화이트보드 설명"><Info :size="18" aria-hidden="true" /></button>
        </UiTooltip>
      </div>
    </section>

    <section class="block">
      <h2>다이얼로그 · 드로어</h2>
      <div class="row">
        <UiDialog v-model:open="cancelOpen" title="예약을 취소할까요?" description="11월 2일 (월) 19:00–21:00 · 망원 프라이빗 시네마">
          <template #trigger><BaseButton variant="secondary">예약 취소</BaseButton></template>
          <p>취소하면 이 시간 칸은 다른 사람이 예약할 수 있게 풀려요.</p>
          <template #actions>
            <BaseButton variant="quiet" @click="cancelOpen = false">그대로 두기</BaseButton>
            <BaseButton @click="cancelReservation">예약 취소</BaseButton>
          </template>
        </UiDialog>
        <UiDrawer v-model:open="filterOpen" title="필터" side="bottom">
          <template #trigger><BaseButton variant="secondary"><Filter :size="18" aria-hidden="true" />모바일 필터</BaseButton></template>
          <UiAccordion :items="[{ value: 'type', title: '유형', body: '스터디룸 · 스튜디오 · 카페 · 강의실 · 파티룸' }, { value: 'facility', title: '시설', body: '화이트보드 · TV · 주차 · 음식 반입' }]" />
        </UiDrawer>
      </div>
    </section>

    <section class="block">
      <h2>아코디언</h2>
      <UiAccordion :items="faq" />
    </section>

    <section class="block">
      <h2>스켈레톤</h2>
      <div class="sk">
        <UiSkeleton height="120px" radius="var(--r-lg)" />
        <UiSkeleton width="60%" height="20px" />
        <UiSkeleton width="40%" height="20px" />
      </div>
    </section>

    <section class="block">
      <h2>스플릿 레이아웃</h2>
      <SplitLayout ratio="3fr 2fr">
        <template #start><div class="box">본문 (상세 소개, 예약 폼)</div></template>
        <template #end><div class="box box--alt">요약 · 예약 카드</div></template>
      </SplitLayout>
    </section>

    <section class="block">
      <h2>사이드바 레이아웃</h2>
      <SidebarLayout label="필터">
        <template #sidebar><div class="box box--alt">필터 사이드바 (1024px 이상)</div></template>
        <template #mobile-trigger><p class="hint">1024px 아래에서는 사이드바 대신 필터 드로어를 엽니다.</p></template>
        <div class="box">검색 결과</div>
      </SidebarLayout>
    </section>
  </div>
</template>

<style scoped>
.showcase {
  padding-block: var(--sp-48);
}
.title {
  font-size: var(--fs-32);
  font-weight: 900;
}
.lead {
  margin-top: var(--sp-8);
  color: var(--c-muted);
}
.block {
  margin-top: var(--sp-48);
}
.block h2 {
  margin-bottom: var(--sp-16);
  font-size: var(--fs-20);
  font-weight: 800;
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--sp-12);
}
.w160 {
  width: 160px;
}
.icon-btn {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-md);
  background: var(--c-surface);
  cursor: help;
}
.sk {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 420px;
}
.box {
  padding: var(--sp-24);
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.box--alt {
  background: var(--c-brand-soft);
}
.hint {
  margin-bottom: var(--sp-12);
  color: var(--c-muted);
}
</style>
