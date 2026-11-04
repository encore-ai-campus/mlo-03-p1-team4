<template>
  <footer class="footer">
    <div class="container footer__inner">
      <p><strong>공간큐브</strong> (가칭) — 전국 공간을 1시간 단위로 예약</p>
      <p class="footer__muted">화면의 공간·가격·후기는 예시 데이터예요. 결제는 모의 결제로만 동작해요.</p>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  margin-top: var(--sp-64);
  background: var(--c-ink);
  color: var(--c-on-dark-2);
  font-size: var(--fs-13);
}
.footer__inner {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--sp-8) var(--sp-24);
  padding-block: var(--sp-32);
}
.footer strong {
  color: var(--c-on-dark);
}
.footer__muted {
  color: var(--c-on-dark-3);
}
</style>
