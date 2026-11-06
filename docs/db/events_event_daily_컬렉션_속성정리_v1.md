# events와 event_daily 컬렉션 속성 정리

작성일: 2026-11-06

MongoDB 연결은 `1차 프로젝트`, 데이터베이스는 `space_rental_analytics`다. `events`는 행동 한 건씩, `event_daily`는 날짜·행동·공간·테스트 여부별 집계 결과를 저장한다.

| 구분 | events | event_daily |
|---|---|---|
| 목적 | 사용자 행동 원천 기록 | Grafana·발표용 일별 집계 |
| 문서 단위 | 이벤트 1건 | 날짜·행동·공간·테스트 여부 조합 1개 |
| 구조 버전 | `schema_version: 1` | 버전 필드 미정의 |
| 검증 규칙 | 필수 필드·자료형·허용 행동 검사 | 별도 검증 규칙 없음 |
| 보관 기간 | `received_at` 기준 365일 | TTL 없음. 기간에 따른 자동 삭제 없음 |

아래 내용은 앞서 적용·확인한 설정 기준이다. 수집 API·자동 일별 집계·Grafana 연결은 이번 컬렉션 설정 작업에 포함되지 않았다.

## 1. events 기본 속성

`_id`를 제외한 아래 속성은 모두 필수다. 필수 속성은 자동으로 채워지지 않는다. 하위 속성도 지정된 구조를 따라야 하며, 명시한 항목에서만 null을 허용한다.

| 속성 | 자료형 | 설명 |
|---|---|---|
| `_id` | ObjectId | MongoDB 문서 ID. 생략하면 자동 생성 |
| `event_id` | 비어 있지 않은 string | 이벤트 고유 ID. 중복 불가. 재전송 시 동일 값 유지 |
| `schema_version` | int | 현재 `1`만 허용 |
| `event_name` | string enum | 아래 정의된 행동 15종 중 하나 |
| `occurred_at` | date | 행동 발생 시각 |
| `received_at` | date | 서버 수신 시각. TTL 기준 |
| `is_synthetic` | bool | 실제 사용자 false, 테스트·생성 데이터 true |
| `server` | 비어 있지 않은 string | 수집 서버·생성 주체. 예: api-1, api-2, generator, locust |
| `user` | object | 사용자·방문 세션 정보 |
| `site` | object | 접속 서비스·플랫폼 정보 |
| `acquisition` | object | 이번 세션의 최초 유입 정보 |
| `page` | object | 이벤트가 발생한 현재 페이지 |
| `navigation` | object | 현재 페이지에 도달한 직전 이동 경로 |
| `products` | array | 당시 상품·가격·대여 조건 |
| `properties` | object | 이벤트별 추가 정보. 없으면 `{}` |

### 사용자 정보 user

| 속성 | 자료형 | 설명 |
|---|---|---|
| `user_id` | 비어 있지 않은 string 또는 null | 로그인 시 회원 ID, 비로그인 시 null |
| `anonymous_id` | 비어 있지 않은 string | 브라우저에 유지하는 익명 방문자 식별자 |
| `session_id` | 비어 있지 않은 string | 방문 세션 식별자 |
| `session_sequence` | 1 이상 int 또는 long | 해당 세션 내 이벤트 순서 |

로그인 전후에 `anonymous_id`를 유지하면 행동을 연결할 수 있다. 과거 비로그인 이벤트의 `user_id`를 나중에 덮어쓰지는 않는다. 로그인 상태와 구조 버전은 별개다. 실제 로그인 여부는 수집 서버에서 확인한 인증 정보를 기준으로 기록해야 한다.

### 접속 사이트 site

| 속성 | 자료형·허용 값 | 설명 |
|---|---|---|
| `site_id` | 비어 있지 않은 string | 서비스 사이트 식별자. 예: main |
| `hostname` | 비어 있지 않은 string | 현재 접속 도메인 |
| `platform` | desktop_web / mobile_web / ios / android | 접속 플랫폼 |

사이트별 가격 차등 기능을 뜻하는 속성은 아니다. 외부 유입 사이트는 `acquisition`에 기록한다.

### 최초 유입 acquisition

| 속성 | 자료형 | 설명 |
|---|---|---|
| `landing_url` | 비어 있지 않은 string | 세션에서 최초로 방문한 서비스 페이지 |
| `referrer_url` | string 또는 null | 최초 유입 직전 URL |
| `utm_source` | string 또는 null | 유입 출처 |
| `utm_medium` | string 또는 null | 유입 매체 |
| `utm_campaign` | string 또는 null | 캠페인 |

값이 없는 추적 항목은 null로 저장한다. 최초 유입 정보는 세션 내 페이지 이동 후에도 유지한다.

### 현재 페이지 page

| 속성 | 자료형 | 설명 |
|---|---|---|
| `page_view_id` | 비어 있지 않은 string | 페이지 진입 건별 ID |
| `page_type` | 비어 있지 않은 string | 예: product_detail |
| `url` | 비어 있지 않은 string | 현재 페이지 URL |
| `path` | 비어 있지 않은 string | 현재 페이지 경로 |
| `title` | 비어 있지 않은 string | 페이지 제목 |

페이지 진입마다 새 `page_view_id`를 발급한다. 같은 페이지 안의 상품 조회·클릭은 같은 값을 유지한다. 이는 페이지 조회 건의 식별자이며, 고정된 화면 번호는 아니다.

### 페이지 이동 navigation

| 속성 | 자료형·허용 값 | 설명 |
|---|---|---|
| `from` | object 또는 null | 바로 이전 페이지. 모르면 null |
| `to` | object | 현재 도착 페이지 |
| `navigation_type` | external / internal / direct / reload / history | 이동 유형 |

`from`, `to` 객체는 다음 속성을 모두 포함한다.

| 속성 | 자료형 |
|---|---|
| `page_view_id` | string 또는 null |
| `site_id` | string 또는 null |
| `url` | 비어 있지 않은 string |
| `path` | string 또는 null |

예: 구글 → 검색 결과 → 상품 상세일 때, 상품 상세의 `navigation`은 검색 결과 → 상품 상세다. `acquisition`은 구글에서 검색 결과로 들어온 최초 유입을 유지한다. 페이지 내부 클릭은 새 페이지 이동으로 집계하지 않는다.

### 상품 products

각 상품 객체는 다음 속성을 모두 포함한다.

| 속성 | 자료형 | 설명 |
|---|---|---|
| `product_id` | 비어 있지 않은 string | 상품 ID |
| `product_name` | 비어 있지 않은 string | 당시 상품명 |
| `price` | object | 당시 표시 가격 |
| `rental_conditions` | object | 대여 조건 |

`price`의 속성은 다음과 같다.

| 속성 | 자료형·허용 값 | 설명 |
|---|---|---|
| `currency` | 대문자 3자리 string | 예: KRW |
| `displayed_amount_minor` | 0 이상 int 또는 long | 통화 최소 단위 금액. KRW 100000 = 100,000원 |
| `displayed_text` | 비어 있지 않은 string | 예: 100,000원 / 시간 |
| `billing_unit` | hour / day / night / session / total | 시간당·일당·박당·회당·총액 구분 |

금액은 문자열이 아닌 정수로 저장한다. 상품을 본 당시 표시 가격을 문서에 복사하고, 나중에 현재 상품 가격으로 바꾸지 않는다. 가격 변경·할인·쿠폰·사이트별 차등 가격 전용 속성은 없다.

`rental_conditions`의 속성은 다음과 같다.

| 속성 | 자료형 | 설명 |
|---|---|---|
| `start_at` | date 또는 null | 선택 시작 시각 |
| `end_at` | date 또는 null | 선택 종료 시각 |
| `timezone` | 비어 있지 않은 string | 예: Asia/Seoul |
| `guest_count` | 1 이상 int 또는 long, 또는 null | 선택 인원 |
| `option_ids` | string 배열 | 선택 옵션 ID. 각 원소는 비어 있지 않은 문자열 |

미선택 상태에서는 날짜·인원은 null, 옵션은 `[]`로 보낸다.

### 추가 정보 properties

객체 내부의 추가 속성을 허용한다. 클릭 위치·조회 월·예약 ID·충돌 시간 등 행동별 값을 담는다. 현재 DB는 내부 항목을 필수로 강제하지 않으므로, 수집 API에서 이벤트별로 검사해야 한다.

```javascript
// 예약 충돌의 properties 예시
{
  reason: "SLOT_TAKEN",
  date: "2026-11-10",
  conflicting_hours: [14, 15]
}
```

이름·이메일·비밀번호·토큰 등 개인정보와 인증정보를 추가 정보에 넣지 않는다.

## 2. events 행동 종류

| event_name | 기록 시점 | products 조건 |
|---|---|---|
| `page_view` | 페이지 진입·이동 완료 | 빈 배열 허용 |
| `product_impression` | 상품 카드 화면 노출 | 1개 이상 |
| `product_view` | 상세 상품과 가격 화면 표시 | 1개 이상 |
| `product_section_click` | 설명·주의사항 등 클릭 | 1개 이상 |
| `search_submit` | 검색 실행 | 빈 배열 허용 |
| `availability_view` | 예약 가능한 날짜 화면 표시 | 1개 이상 |
| `rental_slot_select` | 대여 시간대 선택 | 1개 이상 |
| `reservation_start` | 예약 절차 시작 | 1개 이상 |
| `reservation_complete` | 서버에서 예약 확정 확인 | 1개 이상 |
| `reservation_conflict` | 서버에서 예약 시간 중복 확인 | 1개 이상 |
| `reservation_cancel_attempt` | 예약 취소 요청 시도 | 1개 이상 |
| `reservation_cancel_complete` | 서버에서 예약 취소 완료 확인 | 1개 이상 |
| `review_create` | 후기 작성 성공 확인 | 1개 이상 |
| `login` | 로그인 성공 확인 | 빈 배열 허용 |
| `signup` | 회원가입 완료 확인 | 빈 배열 허용 |

허용 이름이 아닌 이벤트는 DB 검증에서 거부한다. 예약 충돌·예약 완료·취소 완료는 버튼 클릭이 아니라 서버 처리 결과를 기준으로 기록한다.

## 3. events 저장 예시

다음은 상품 조회 이벤트의 전체 예시다. MongoDB 셸 표기이며 API JSON 자체는 아니다. 도메인·상품·가격은 예시다.

```javascript
{
  _id: ObjectId(),
  event_id: "evt_550e8400-e29b-41d4-a716-446655440000",
  schema_version: 1,
  event_name: "product_view",
  occurred_at: ISODate("2026-11-06T01:00:00.000Z"),
  received_at: ISODate("2026-11-06T01:00:00.200Z"),
  is_synthetic: false,
  server: "api-1",
  user: {
    user_id: "1",
    anonymous_id: "anon_001",
    session_id: "session_001",
    session_sequence: 3
  },
  site: {
    site_id: "main",
    hostname: "space.example.com",
    platform: "mobile_web"
  },
  acquisition: {
    landing_url: "https://space.example.com/search",
    referrer_url: "https://www.google.com/",
    utm_source: null,
    utm_medium: null,
    utm_campaign: null
  },
  page: {
    page_view_id: "pv_002",
    page_type: "product_detail",
    url: "https://space.example.com/spaces/56619",
    path: "/spaces/56619",
    title: "압구정 팝업 공간"
  },
  navigation: {
    from: {
      page_view_id: "pv_001",
      site_id: "main",
      url: "https://space.example.com/search",
      path: "/search"
    },
    to: {
      page_view_id: "pv_002",
      site_id: "main",
      url: "https://space.example.com/spaces/56619",
      path: "/spaces/56619"
    },
    navigation_type: "internal"
  },
  products: [{
    product_id: "56619",
    product_name: "압구정 팝업 공간",
    price: {
      currency: "KRW",
      displayed_amount_minor: NumberLong("100000"),
      displayed_text: "100,000원 / 시간",
      billing_unit: "hour"
    },
    rental_conditions: {
      start_at: null,
      end_at: null,
      timezone: "Asia/Seoul",
      guest_count: null,
      option_ids: []
    }
  }],
  properties: {}
}
```

## 4. event_daily 속성

현재 `event_daily`에는 별도 Validation 규칙이 없다. 아래 자료형과 `count`는 집계 구현 시 사용할 권장 형식이며, DB가 필수 필드나 자료형을 강제하는 상태는 아니다. 실제 설정된 것은 기본 인덱스와 네 필드의 복합 고유 인덱스다.

| 속성 | 권장 자료형 | 설명 | 현재 DB 설정 |
|---|---|---|---|
| `_id` | ObjectId | 문서 ID | 생략하면 자동 생성 |
| `date` | string | 집계 날짜. 예: 2026-11-06 | 고유 인덱스 구성 항목 |
| `event_type` | string | 집계한 행동 종류. 예: product_view | 고유 인덱스 구성 항목 |
| `venue_id` | string 또는 null | 공간 ID. 원천 product_id와 자료형 통일 권장 | 고유 인덱스 구성 항목 |
| `is_synthetic` | bool | 실제·테스트 데이터 구분 | 고유 인덱스 구성 항목 |
| `count` | 0 이상 int 또는 long | 해당 조합의 발생 횟수 | 검증 규칙 없음 |

저장 예시:

```javascript
{
  _id: ObjectId(),
  date: "2026-11-06",
  event_type: "product_view",
  venue_id: "56619",
  is_synthetic: false,
  count: NumberLong("150")
}
```

의미: 2026년 11월 6일 실제 사용자의 공간 56619 상품 조회가 150건 발생했다.

로그인·가입처럼 상품이 없는 이벤트의 `venue_id`를 null로 저장하는 정책, 집계 날짜의 시간대, 상품 배열을 펼칠 때의 집계 단위는 집계 코드 구현 시 확정해야 한다. 예시 날짜 형식은 YYYY-MM-DD이며, 한국 서비스의 날짜 집계는 Asia/Seoul 기준으로 맞추는 것을 권장한다.

## 5. 원천과 집계 필드 대응

| events | event_daily | 처리 |
|---|---|---|
| `occurred_at` | `date` | 합의한 시간대로 날짜 변환 |
| `event_name` | `event_type` | 행동 이름 전달 |
| `products[].product_id` | `venue_id` | 공간 ID 전달. 상품 없는 이벤트는 별도 정책 필요 |
| `is_synthetic` | `is_synthetic` | 실제·테스트를 분리 집계 |
| 같은 조합의 원천 기록 | `count` | 집계 단위에 따라 건수 계산 |

컬렉션을 생성하는 것만으로 집계가 실행되지는 않는다. 집계 작업과 스케줄러는 별도로 구현해야 한다. 재집계 시 같은 조합의 문서를 갱신하는 방식을 사용해 중복 합산을 방지한다.

## 6. 검증과 인덱스

### events

- `validationLevel: "strict"`, `validationAction: "error"`
- 필수 필드 누락·자료형 오류·허용되지 않은 행동은 저장 거부
- 기본 구조와 주요 하위 객체의 임의 필드 추가 차단. `properties` 내부는 유연하게 허용
- 현재 구조 버전은 사용자 요청에 따라 초기 확정 버전 `1`로 유지
- 로그인·가입 성공 여부, 실제 표시 가격 등의 사실 확인은 서비스 로직에서 처리
- `is_synthetic`과 `server`에는 자동 기본값이 없으므로 수집 서버에서 설정

| 인덱스 | 키 | 설정 |
|---|---|---|
| `_id_` | `{ _id: 1 }` | 기본 고유 인덱스 |
| `uq_event_id` | `{ event_id: 1 }` | 고유 인덱스 |
| `user_history` | `{ "user.user_id": 1, occurred_at: -1 }` | 사용자별 이력 |
| `session_order` | `{ "user.session_id": 1, "user.session_sequence": 1 }` | 세션 내 순서 |
| `site_product_history` | `{ "site.site_id": 1, "products.product_id": 1, occurred_at: -1 }` | 사이트·상품별 이력 |
| `ttl_received_at_365d` | `{ received_at: 1 }` | expireAfterSeconds: 31536000 |

원천 이벤트는 서버 수신 시각으로부터 365일이 지나면 자동 삭제 대상이 된다. TTL 삭제는 백그라운드에서 처리되므로 정확히 만료되는 순간 삭제됨을 보장하지 않는다. 실제·테스트 데이터 모두 동일하게 적용된다.

### event_daily

```javascript
db.event_daily.createIndex(
  { date: 1, event_type: 1, venue_id: 1, is_synthetic: 1 },
  { unique: true }
);
```

같은 날짜·행동·공간·테스트 여부 조합은 중복 저장할 수 없다. 고유 인덱스는 필드의 존재나 자료형을 강제하지 않는다. 기본 `_id_` 인덱스도 존재한다. TTL이 없으므로 기간에 따른 자동 삭제는 없다.
