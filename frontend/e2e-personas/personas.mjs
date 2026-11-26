// Markdown 자유문을 자동 해석하지 않고 확인한 조건을 명시적으로 연결한다.
// 11-09 PM 결정: 실서버에 있는 지역(서울·인천·부산·충남·경기)에 맞춰 시도를 옮긴다. 원본 문서의 시도는 sourceSido로 남긴다.
// 인원·예산·시간 길이·결제수단은 원본 그대로 두고, 시작 시각만 공간 운영 시간에 맞춘 경우 사유를 note에 적는다.
const weekdays = [1, 2, 3, 4, 5]
export const personas = [
  { id: 'study', name: '이도겸', source: '학습·스터디형/이도겸.md', categories: ['studyroom'], sido: '서울', sourceSido: '부산', people: 2, start: 16, hours: 1, budget: 20000, weekdays, method: 'phone', prerequisites: '최소1시간·의자/테이블·인터넷 확인', note: '부산에는 스터디룸이 없어 서울로 이동' },
  { id: 'work', name: '유태욱', source: '업무·협업형/유태욱.md', categories: ['studyroom'], sido: '인천', sourceSido: '인천', people: 1, start: 11, hours: 1, budget: 35000, weekdays, method: 'card', prerequisites: '인터넷·전기·정시 일정 확인' },
  { id: 'photo', name: '차민재', source: '촬영·창작형/차민재.md', categories: ['studio'], sido: '인천', sourceSido: '인천', people: 3, start: 11, hours: 4, budget: 200000, weekdays, method: 'card', prerequisites: '상품 도착·사진가 일정·반입 안내·의자/테이블·전기 확인', note: '인천 스튜디오가 11시에 열어 시작을 9시→11시로 조정' },
  { id: 'workshop', name: '이아진', source: '강의·워크숍형/이아진.md', categories: ['lectureroom', 'cafe'], sido: '충남', sourceSido: '서울', people: 8, start: 14, hours: 3, budget: 90000, weekdays: [0], method: 'transfer', prerequisites: '진행자 포함 최소6명 참가 확정·계획8명 수용·의자/테이블 확인', note: '서울 강의실은 3시간 예산 초과, 카페는 16시 마감이라 충남으로 이동' },
  { id: 'gathering', name: '배진수', source: '친목·기념일형/배진수.md', categories: ['cafe', 'partyroom'], sido: '서울', sourceSido: '대구', people: 6, start: 18, hours: 4, budget: 160000, weekdays: [6], method: 'transfer', prerequisites: '모임 일정·의자/테이블·이용 안내 확인', note: '대구 공간이 없어 서울로 이동' },
  { id: 'browse', name: '백나연', source: '검색전용/백나연.md', categories: ['studyroom'], sido: '경기', sourceSido: '대전', people: 2, start: 10, hours: 2, budget: 30000, weekdays: [6], browseOnly: true, prerequisites: '유료 예약 없이 도서관 대안 확보 후 탐색 종료', note: '대전 공간이 없어 경기로 이동' },
]

// 실제 DB 시드의 명칭을 사용한다. 목업 별칭(와이파이·콘센트)으로 바꾸지 않는다.
export const requiredFacilities = {
  study: ['인터넷/WIFI', '의자/테이블'], work: ['인터넷/WIFI', '전기'],
  photo: ['전기', '의자/테이블'], workshop: ['의자/테이블'], gathering: ['의자/테이블'], browse: [],
}

// 첫 주 날짜에 빈 시간이 없으면 같은 요일로 몇 주까지 더 찾아볼지, 한 검색에서 상세를 몇 곳까지 비교할지.
export const searchDepth = { weeks: 3, candidates: 4 }
