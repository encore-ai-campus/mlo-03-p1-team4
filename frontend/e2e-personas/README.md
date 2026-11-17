# 대표 페르소나 실서버 시험

기존 `e2e/` 목업 회귀와 분리된 실서버 전용 시험이다. 원본은 `simulator/locust/personas/`의 승인된 문서이며 6명의 조건을 `personas.mjs`에 명시적으로 연결한다. 500명 전체는 `personas500.mjs`가 문서에서 유형·지역·인원만 규칙으로 뽑아 `persona500.spec.mjs`(읽기 전용)로 돌린다(`PERSONA_SET=500`).

실행 안내: [노진산 PC 준비](../../docs/Playwright_대표6명_실행준비.md).
정책 검증: `node --test frontend/e2e-personas/policy.test.mjs`.
목록 확인: `frontend/run-personas.ps1` (서버 접속 없음). 6명 동시 실행·사람별 녹화: `-Parallel -Record`.

읽기는 비회원 탐색 부분 시험, 쓰기는 기존 합성 계정의 로그인→예약→취소 시험이다. 시설/안내/상품 도착/참가 확정 같은 정성적 조건은 실행자가 원본을 보고 확인해야 한다. 조건 불일치를 임의로 완화하지 않는다. 재고 부족 skip은 완료가 아니다.
