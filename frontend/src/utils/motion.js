// 움직임 줄이기 설정이면 JS 스크롤도 바로 이동한다 (CSS scroll-behavior는 scrollIntoView·scrollBy의 behavior 옵션을 못 막는다)
export const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
export const scrollBehavior = () => (prefersReducedMotion() ? 'auto' : 'smooth')
