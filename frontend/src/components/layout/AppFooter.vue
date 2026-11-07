<script setup>
// 공통 푸터 (디자인 캔버스 SiteFooter 시안): 서비스 소개 · 바로가기 · 프로젝트 · 안내 + 캠프 표기
const links = [
  { to: '/search', label: '공간 찾기' },
  { to: '/me', label: '예약 내역' },
  { to: '/reviews', label: '후기 모아보기' },
  { to: '/login', label: '로그인 · 회원가입' },
]
const REPO = 'https://github.com/encore-ai-campus/mlo-03-p1-team4'
</script>

<template>
  <footer class="footer">
    <div class="container footer__inner">
      <div class="footer__cols">
        <section class="footer__about" aria-label="서비스 소개">
          <RouterLink to="/" class="footer__logo">
            <span class="footer__mark" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" /></svg>
            </span>
            <span class="footer__name">다락큐브</span>
          </RouterLink>
          <p>스터디룸 · 스튜디오 · 카페 · 강의실 · 파티룸을 전국에서 찾아 1시간 단위로 예약하는 공간대여 서비스예요.</p>
        </section>

        <nav class="footer__col" aria-label="서비스 바로가기">
          <h2>서비스</h2>
          <RouterLink v-for="l in links" :key="l.to" :to="l.to">{{ l.label }}</RouterLink>
        </nav>

        <section class="footer__col" aria-label="프로젝트">
          <h2>프로젝트</h2>
          <span>팀 방조 · 노진산 · 이자연 · 이세훈 · 전희정</span>
          <span>역할 프론트·PM 1 · FastAPI 2 · DB 1</span>
          <span>Vue 3 · FastAPI · MariaDB · MongoDB · HAProxy · Nginx</span>
          <span>배포 노트북 4대 · VM 7대 (로컬)</span>
          <a href="/photos/credits.html">사진 출처 · 라이선스</a>
          <a :href="REPO" target="_blank" rel="noopener noreferrer">GitHub 저장소</a>
          <a :href="`${REPO}/wiki`" target="_blank" rel="noopener noreferrer">프로젝트 위키</a>
        </section>

        <section class="footer__col" aria-label="안내">
          <h2>안내</h2>
          <span>결제는 모의 결제라 실제 돈이 나가지 않아요.</span>
          <span>공간 정보는 공개 자료를 가공한 예시예요. 업체 실명·실제 공간 사진은 표시하지 않으며, 유형별 분위기 참고 사진과 일러스트를 사용해요.</span>
          <span>탈퇴하면 이름 · 연락처 · 생년월일은 바로 지워져요.</span>
        </section>
      </div>

      <div class="footer__bottom">
        <div class="footer__camp">
          <strong>[SK네트웍스 Family 엔코아AI캠퍼스] AI 레디 데이터 엔지니어링 캠프 3기 1차 프로젝트</strong>
          <span>© 2026 팀 방조</span>
        </div>
        <span class="footer__faint">발표 2026-11-09</span>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  margin-top: var(--sp-64);
  background: var(--c-ink);
  color: var(--c-on-dark-2);
  font-size: var(--fs-13);
  line-height: 1.6;
}
.footer__inner {
  display: flex;
  flex-direction: column;
  gap: var(--sp-32);
  padding-block: var(--sp-48) var(--sp-24);
}
.footer__cols {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-32) var(--sp-48);
}
.footer__about {
  flex: 2 1 280px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-12);
}
.footer__about p {
  margin: 0;
  max-width: 360px;
}
.footer__logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  align-self: flex-start;
  color: var(--c-on-dark);
  text-decoration: none;
}
.footer__mark {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--c-brand);
  display: grid;
  place-items: center;
}
.footer__name {
  font-weight: 900;
  font-size: 1.125rem;
  letter-spacing: -0.02em;
}
.footer__col {
  flex: 1.4 1 200px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.footer__col:first-of-type {
  flex: 1 1 140px;
}
.footer__col h2 {
  margin: 0 0 var(--sp-4);
  font-size: var(--fs-13);
  font-weight: 700;
  color: var(--c-on-dark);
}
.footer__col a {
  align-self: flex-start;
  color: var(--c-on-dark-2);
  text-decoration: none;
  transition: color var(--t-fast) var(--ease-out);
}
.footer__col a:hover {
  color: var(--c-on-dark);
  text-decoration: underline;
}
.footer__bottom {

  padding-top: var(--sp-16);
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--sp-12) var(--sp-24);
}
.footer__camp {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.footer__camp strong {
  color: var(--c-on-dark);
  font-weight: 700;
}
.footer__camp span,
.footer__faint {
  color: var(--c-on-dark-3);
}
</style>
