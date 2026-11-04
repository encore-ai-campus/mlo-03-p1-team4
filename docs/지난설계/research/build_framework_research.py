from pathlib import Path
from html import escape
import base64
import re
import json
from bs4 import BeautifulSoup

PROJECT=Path(r'C:\MLops03\Pro_1')
ROOT=Path(__file__).resolve().parent
MAIN=PROJECT/'맛집_MVP_설계_리뷰_브리핑.html'
OUT=PROJECT/'크롤링_로그_프레임워크_사전조사.html'
existing=BeautifulSoup(MAIN.read_text(encoding='utf-8'),'html.parser')
css=existing.select_one('head > style').get_text()

def cite(url,label='공식 문서'):
    return f'<a href="{url}" target="_blank" rel="noreferrer">{label} ↗</a>'
def p(s):return '<p>'+s+'</p>'
def table(head,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def note(s):return '<aside class="callout">'+s+'</aside>'
def strip_imports(s):return re.sub(r'''@import\s+(?:url\([^)]*\)|"[^"]*"|'[^']*')\s*;?''','',s,flags=re.I)
def diagram(name,title):
    svg=strip_imports((ROOT/(name+'.svg')).read_text(encoding='utf-8'))
    mmd=(ROOT/(name+'.mmd')).read_text(encoding='utf-8')
    return f'<figure><div class="figure-title">{title}<a download="{name}.svg" href="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}">SVG 저장 ↓</a></div><div class="diagram">{svg}</div><details><summary>Mermaid 원본</summary><pre>{escape(mmd)}</pre></details></figure>'

urls={
 'httpx':'https://www.python-httpx.org/async/',
 'timeout':'https://www.python-httpx.org/advanced/timeouts/',
 'retry':'https://www.python-httpx.org/advanced/transports/',
 'bs4':'https://www.crummy.com/software/BeautifulSoup/bs4/doc/',
 'scrapy':'https://docs.scrapy.org/en/latest/intro/overview.html',
 'throttle':'https://docs.scrapy.org/en/latest/topics/autothrottle.html',
 'settings':'https://docs.scrapy.org/en/latest/topics/settings.html',
 'playwright':'https://playwright.dev/python/docs/intro',
 'logging':'https://docs.python.org/3/library/logging.html',
 'structlog':'https://www.structlog.org/en/stable/',
 'loki':'https://grafana.com/docs/loki/latest/get-started/overview/',
 'alloy':'https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.docker/',
 'labels':'https://grafana.com/docs/loki/latest/get-started/labels/bp-labels/',
 'promtail':'https://grafana.com/docs/loki/latest/send-data/promtail/',
 'postgres':'https://grafana.com/docs/grafana/latest/datasources/postgres/configure/',
 'scheduler':'https://apscheduler.readthedocs.io/en/3.x/faq.html',
 'prometheus':'https://prometheus.io/docs/introduction/overview/',
 'retention':'https://grafana.com/docs/loki/latest/operations/storage/retention/',
 'auth':'https://grafana.com/docs/loki/latest/operations/authentication/',
}

one=note('<strong>추천 결론</strong> · 공공 API와 소수의 허락된 페이지는 HTTPX + Beautiful Soup으로 수집한다. 사용자 활동·감사·수집 결과는 PostgreSQL에 보관한다. API·worker의 운영 로그를 모아 보고 싶다면 structlog → Grafana Alloy → Loki → Grafana를 추가한다. 설치·성능 검증 전의 사전조사 권고안이다.')
one+=table(['구분','실제 역할','이번 프로젝트에서의 위치'],[
 ['크롤링','외부 페이지를 읽고 필요한 데이터를 추출','HTTPX + Beautiful Soup / 필요 시 Scrapy·Playwright'],
 ['사용자 활동 데이터','누가 어떤 식당을 조회·검색·리뷰 작성했는지 기록','PostgreSQL user_events. 서비스 지표의 기준 데이터'],
 ['변경 감사','누가 어떤 내용을 변경·삭제했는지 기록','PostgreSQL audit_logs. CRUD와 같은 트랜잭션'],
 ['수집 실행 결과','어떤 작업에서 몇 건 삽입·갱신·실패했는지 기록','PostgreSQL crawl_jobs. 재시도·검수 화면의 기준'],
 ['운영 로그','왜 요청이 실패했는지·어느 수집 단계가 깨졌는지 추적','JSON stdout → Alloy → Loki → Grafana'],
 ['운영 메트릭','요청량·오류율·지연시간 같은 시간별 수치 관찰','필요할 때 Prometheus 추가. 1차 필수는 아님'],
])
one+=p('Loki에서도 로그 기반 건수·비율을 계산할 수 있다. 따라서 사용자 활동 분석이 “불가능”한 것은 아니다. 다만 회원·식당·리뷰와 연결하고, 중복·탈퇴·트랜잭션 일관성을 관리해야 하는 이 프로젝트에서는 관계형 DB가 원본 보관소로 더 잘 맞는다는 판단이다. Loki는 라벨로 스트림을 찾고 로그 본문을 읽는 구조다. '+cite(urls['loki']))

two=table(['후보','분류·가능한 일','잘 맞는 조건','추가 부담·한계','판단 / 근거'],[
 ['HTTPX','HTTP 클라이언트. 동기·비동기 요청, JSON/API·HTML 다운로드','공공 API 중심, 소수 출처, 수집 로직을 직접 제어','크롤링 큐·중복 필터·robots·속도 제한은 직접 설계해야 함','기본 채택 권고 · '+cite(urls['httpx'])],
 ['Beautiful Soup 4','HTML/XML 파서. CSS 선택자·태그로 필요한 필드 추출','서버가 반환한 HTML에 메뉴/주소가 들어 있음','직접 HTTP 요청하거나 JavaScript를 실행하는 도구가 아님','HTTPX와 조합 · '+cite(urls['bs4'])],
 ['Scrapy','크롤링 프레임워크. Spider·요청 스케줄링·추출 구조 제공','여러 출처·페이지 순회·반복 수집 규칙이 복잡해짐','프로젝트 구조와 실행 모델 학습 필요. JS 렌더링은 별도 브라우저 연동 검토','출처 확대 시 대안 · '+cite(urls['scrapy'])],
 ['Playwright Python','브라우저 자동화. 실제 렌더링·클릭·페이지 조작','허락된 사이트인데 JS 실행 후에만 데이터가 표시됨','브라우저 설치·컨테이너 의존성·실행 자원·대기 로직 필요. 자원 수치는 실측 필요','필요한 출처에만 선택 · '+cite(urls['playwright'])],
])
two+=diagram('crawler-dataflow','데이터 형태에 따라 도구를 선택한다')
two+=p('<strong>공공 API는 JSON을 바로 파싱한다.</strong> HTML이 아니므로 Beautiful Soup을 거칠 이유가 없다. HTML 정적 페이지에는 HTTPX + Beautiful Soup, JS가 필수인 허락된 페이지에는 Playwright를 선택한다. “어떤 사이트를 수집할지”가 정해지기 전에 브라우저 자동화를 기본값으로 고정하지 않는다.')
two+=p('Scrapy의 AutoThrottle은 응답 지연을 참고해 요청 간격을 조정하고 동시성/다운로드 지연 설정을 따른다. robots 관련 설정도 제공하지만, robots 준수와 저장·재게시 허락은 별도 확인 사항이다. '+cite(urls['throttle'],'AutoThrottle')+' · '+cite(urls['settings'],'Scrapy 설정'))
two+=note('<strong>HTTPX 재시도 주의</strong> · HTTPTransport(retries=…)는 연결 오류/연결 타임아웃에 대한 재시도다. 429·503·읽기 타임아웃까지 자동 처리한다고 가정하면 안 된다. 프로젝트의 상태코드별 백오프·Retry-After 정책을 별도로 구현한다. '+cite(urls['retry'],'HTTPX transports')+' · '+cite(urls['timeout'],'타임아웃'))

three=table(['도구','담당하는 역할','우리 프로젝트의 선택','근거'],[
 ['Python logging','앱/외부 라이브러리 로그 생성·레벨·핸들러','기본 기반으로 사용. 필요한 필드를 JSON 한 줄로 통일','표준 라이브러리 · '+cite(urls['logging'])],
 ['structlog','구조화된 키·값 로그, JSON 출력, 표준 logging 연동','request_id·job_id·component를 일관되게 붙이고 싶으면 채택','Python 로그 생성 도구 · '+cite(urls['structlog'])],
 ['Grafana Alloy','Docker 등에서 운영 로그를 읽고 Loki에 전달','Loki를 쓸 경우 수집기로 검토','로그 수집·전송 담당 · '+cite(urls['alloy'])],
 ['Grafana Loki','로그 저장·검색·LogQL 기반 로그 집계','운영 오류·예외·수집 단계 추적에 사용','로그 보관/쿼리 담당 · '+cite(urls['loki'])],
 ['Grafana','Loki/DB 등을 조회하는 대시보드','운영 대시보드. PostgreSQL도 직접 데이터 소스로 연결 가능','화면·조회 담당 · '+cite(urls['postgres'])],
 ['Prometheus','시간별 메트릭 수집·질의','요청 지연/오류율 모니터링이 별도 목표일 때 추가','원문 사용자 이벤트 보관 대체로 쓰지 않음 · '+cite(urls['prometheus'])],
])
three+=p('위 제품들은 같은 기능을 놓고 고르는 경쟁 도구가 아니다. structlog가 로그를 만들고, Alloy가 읽어 전달하고, Loki가 보관/질의하며, Grafana가 보여주는 관계다. Grafana를 쓴다고 로그 저장소가 자동으로 생기거나 DB의 사용자 이벤트가 자동 수집되는 것은 아니다.')
three+=note('<strong>2026-10-29 확인</strong> · Promtail은 2026-03-02 EOL에 도달했고 향후 지원·업데이트가 제공되지 않는다. 오래된 Loki + Promtail 예제를 신규 구성의 기준으로 삼지 않는다. '+cite(urls['promtail'],'Promtail 종료 공식 문서'))

four=diagram('log-dataflow','분석용 기록과 장애 추적용 로그의 흐름')
four+=table(['발생 사례','DB에 남길 내용','Loki에 남길 내용','수집 책임'],[
 ['식당 상세 조회','user_events.restaurant_view, restaurant_id, received_at','필요한 HTTP 결과·request_id·duration_ms','서버에서 기록. 프론트가 같은 view를 중복 전송하지 않음'],
 ['검색·필터','user_events.restaurant_search, 필터 종류·결과 수','경로 템플릿·처리시간, 원문 검색어는 제외','서버. 요청 query string 전체 로깅하지 않음'],
 ['리뷰 작성/수정/삭제','리뷰 행 + user_events + audit_logs','review_create 처리 성공/실패와 request_id, 본문 제외','서버. 세 기록은 동일 DB 트랜잭션'],
 ['즐겨찾기 추가/취소','실제 상태 변경이 있을 때만 이벤트','HTTP/예외 요약','서버. 멱등 재요청은 행동 이벤트 중복 생성 금지'],
 ['외부링크·목록/지도 클릭','클라이언트 이벤트 ID로 중복 제거, 로그인 user_id는 서버 파생','분석 이벤트 전체를 운영 로그로 복제할 필요 없음','프론트 배치 → /events, 로그인 상태 CSRF 조건 유지'],
 ['공공 API 503·수집 파싱 실패','crawl_jobs 상태·재시도·실패코드·적재 건수','job_id·출처 코드·실패 단계·정제된 예외','worker. 원문 URL 키·응답 전문 제외'],
])
four+=p('Alloy/Loki 장애가 사용자의 리뷰 저장을 직접 실패시키지 않도록, 요청 처리 중 Loki HTTP 전송 성공을 기다리는 구조는 피한다. 앱은 stdout으로 로그를 출력하고 수집기가 전달한다. 반면 리뷰 변경과 감사 DB 기록은 하나라도 실패하면 같은 트랜잭션을 취소한다. 두 종류 기록의 신뢰성 요구가 다르기 때문이다.')
four+=p('수집기가 있다고 로그의 무손실·정확히 한 번 전달이 자동 보장되는 것은 아니다. Docker 로그 회전, 수집기 재시작 위치, 버퍼, Loki 중단 시간을 포함해 중복·유실을 검증해야 한다. 운영 로그의 건수를 서비스의 유일한 리뷰/즐겨찾기 원장으로 쓰지 않는 이유다.')

five=table(['후보','언제 적합한가','운영 방식 권고','판단'],[
 ['CRON + Python 명령','매일/매시간처럼 고정된 소수 작업','Linux scheduler 컨테이너 1개에서 DB 작업 예약. worker가 실제 수집','기존 설계 유지 권고. Windows 호스트에 cron이 있다고 가정하지 않음'],
 ['APScheduler 3.x','Python에서 시간대·미실행 처리 등 스케줄 규칙을 관리','FastAPI 웹 worker와 분리한 scheduler 프로세스 1개에서 실행','대안. 3.x 전용 문서를 기준으로 구현·버전 고정'],
 ['더 큰 작업 플랫폼','복잡한 의존 DAG나 여러 서버의 작업 처리가 실제로 필요해짐','도입 비용을 견적낸 뒤 별도 결정','현재는 Celery/Airflow/Redis 등을 선행 도입하지 않음'],
])
five+=p('APScheduler 3.x 공식 FAQ는 여러 프로세스가 같은 영속 job store를 공유하면 중복 실행/누락이 발생할 수 있다고 설명한다. 웹 서버 worker마다 scheduler를 시작하는 방식을 피하고 전용 프로세스로 분리한다. 이 주의는 명시적으로 3.x 기준이며 다른 major 버전의 실행 모델에 그대로 일반화하지 않는다. '+cite(urls['scheduler']))
five+=p('스케줄러는 “언제 작업을 예약할지”, 수집 worker는 “예약된 작업을 어떻게 실행할지”를 맡는다. 어느 스케줄러를 쓰든 DB의 동일 출처·지역 활성 작업 UNIQUE 제약, 실행 잠금, 작업 상태, 재실행 가능한 upsert는 유지해야 한다.')

six=table(['주제','권장','피할 것'],[
 ['Loki 라벨','service_name, env, component 같은 값 종류가 작은 항목','user_id, restaurant_id, request_id, job_id, 전체 URL을 라벨로 지정'],
 ['상세 추적','request_id·job_id는 JSON 본문/필요 시 structured metadata, 같은 ID로 검색','사용자 식별자를 장애 추적에 불필요하게 복제'],
 ['로그 내용','timestamp·level·event·duration_ms·error_code·출처 코드','Authorization·Cookie·비밀번호·API key·사진·리뷰/검색 원문'],
 ['라우트','/restaurants/{restaurant_id}처럼 경로 템플릿 사용','식당 ID마다 다른 URL을 라벨로 만들기'],
 ['보유기간','운영 로그 7~14일을 초기 제안하고 실제 retention 설정 검증','“Loki 설치하면 자동으로 일정 기간 뒤 삭제”라고 가정'],
 ['접근','내부 네트워크로 두고 공개 접근 시 인증 계층 구성','Loki의 tenant 헤더를 사용자 로그인 인증으로 오해'],
])
six+=p('라벨 조합이 늘면 로그 스트림이 급증하므로 고유 ID는 인덱스 라벨로 만들지 않는다. '+cite(urls['labels'],'Loki 라벨 가이드'))
six+=p('Loki는 기본적으로 compactor retention 설정이 활성화되어 있지 않으므로 보유기간 정책을 명시해야 한다. 7~14일은 프로젝트 제안값이며 법정 기간이 아니다. '+cite(urls['retention'],'보유기간 설정'))
six+=p('Loki에는 기본 애플리케이션 인증 계층이 포함되지 않는다. 공개 노출이 필요하면 인증 프록시 등 접근 경로를 설계한다. '+cite(urls['auth'],'인증 구성'))
sample={'timestamp':'2026-10-29T03:00:00Z','level':'error','event':'crawl_fetch_failed','service_name':'restaurant-worker','component':'collector','env':'dev','job_id':'00000000-0000-4000-8000-000000000001','source_code':'semas','stage':'fetch','status_code':503,'attempt':2,'error_code':'UPSTREAM_UNAVAILABLE'}
six+='<h3>운영 로그 필드 예시 · 가상 데이터</h3><pre>'+escape(json.dumps(sample,ensure_ascii=False,indent=2))+'</pre>'
six+=p('위 예시에서 Loki 라벨은 service_name·env·component만 제안한다. job_id·error_code 등은 JSON 본문에 남긴다. 실제 구성에서의 파싱·검색 성공은 아직 검증하지 않았다.')

seven=table(['구성안','포함 항목','장점','추가 부담','추천 조건'],[
 ['A · 기능 완성 우선','HTTPX + Beautiful Soup + PostgreSQL + logging(JSON) + CRON','의존성·배포 부품을 줄이고 원문 12단계 E2E에 집중','여러 컨테이너 로그를 한 화면에서 찾기는 불편','현재 4명·4주 가정의 기본안'],
 ['B · 운영 로그까지 시연','A + structlog + Alloy + Loki + Grafana','API·worker 오류 추적과 로그 대시보드를 발표 가능','Alloy·Loki·Grafana 설정/저장소/보유기간/재시작 검증 필요','운영 관측이 학습 목표이고 담당자를 정할 수 있을 때'],
 ['C · 크롤링 확대','A 또는 B의 수집부를 Scrapy 중심으로 확장, JS에만 Playwright','출처별 Spider·반복 순회를 체계화','프레임워크와 브라우저 연동까지 동시에 배우면 범위 증가','허락된 출처의 수·탐색 규칙이 실제로 복잡해질 때'],
])
seven+=note('<strong>이번 프로젝트 권고</strong> · 먼저 A로 수집→DB→화면→CRUD→활동 기록을 연결한다. 그다음 B를 붙이면 기존 user_events·audit_logs·crawl_jobs 설계를 바꾸지 않고 운영 로그 관찰 기능을 추가할 수 있다. Loki 도입을 결정해도 기존 DB 테이블은 유지한다.')
seven+=p('Grafana에서 사용자 활동 차트를 보여주고 싶으면 PostgreSQL 데이터 소스를 추가하면 된다. 전체 앱 DB 계정을 연결하지 않고, 필요한 집계 뷰에 SELECT만 허용한 전용 계정을 쓴다. 서비스 내부 관리자 화면은 기존 FastAPI 통계 API로 유지할 수 있다. '+cite(urls['postgres'],'Grafana PostgreSQL 연결'))
seven+=p('각 구성의 메모리·CPU·개발 소요시간·실제 처리량은 측정하지 않았다. 숫자 점수나 “몇 배 빠름”을 근거 없이 붙이지 않았다. 패키지와 이미지 버전은 조사 시점의 latest 링크를 그대로 설치하지 말고, 선택한 안정 버전끼리 확인한 뒤 고정해야 한다.')

eight=table(['검증 실험','확인할 내용','합격 기준'],[
 ['공공 API 1개','정상·기관 업무오류·429·503·timeout','허용된 데이터만 저장, 재시도 제한, 실패코드·job 상태 보존'],
 ['허락된 HTML 1개','필드 추출·누락·구조 변경·빈 결과','구조 변경을 “식당 0개 성공”으로 오인하지 않고 실패/검수 처리'],
 ['동일 데이터 재수집','동일 출처 ID·변경된 필드·관리자 잠금','중복 행 없음, 변경값 반영, 관리자 잠금 보존'],
 ['사용자 이벤트','클릭 재전송·리뷰 성공/rollback','event_id 중복 제거, 성공한 CRUD만 DB 이벤트·감사 기록'],
 ['Alloy → Loki','API/worker 로그·request_id/job_id 상관 검색','필요 필드 검색 가능, 비밀값 없음, ID 라벨 없음'],
 ['Loki 중단·재시작','로그 전달 장애와 앱 기능의 관계','리뷰 저장은 계속 가능, 버퍼/재전송·중복/유실 한계 기록'],
 ['일별 통계 교차 검증','DB 집계와 관리자/Grafana 표시','KST 날짜 경계·0건·완료 작업 분모가 설계와 일치'],
 ['보관·복구','로테이션·retention·볼륨·수집기 위치','설정한 보유기간, 재시작 뒤 조회, 실제 파일/로그 정리 확인'],
])
eight+=p('현재는 공식 문서 기반 사전조사만 완료했다. 라이브러리 설치, 실사이트 수집, Loki/Alloy/Grafana 기동, 부하·장애 테스트는 수행하지 않았다. 외부 API를 호출하는 수집 코드의 장애 실험 단계에서는 Postman api-simulation 워크플로를 적용한다. 조사 결과를 API 계약 변경으로 간주하지 않으며 기존 openapi.json은 수정하지 않았다.')
eight+='<h3>공식 문서 목록 · 확인일 2026-10-29</h3>'+table(['대상','공식 근거'],[[k,cite(v,v)] for k,v in urls.items()])

parts=[('Loki의 역할부터 구분','사용자 활동 원본과 운영 로그 검색을 분리한다.',one),('크롤링 도구 비교','공공 API·정적 HTML·동적 페이지는 수집 방식이 다르다.',two),('로그 도구 비교','로그 생성·수집·저장·시각화를 각각 구분한다.',three),('사용자 활동과 운영 로그','같은 요청에서 나와도 저장 목적과 일관성 요구가 다르다.',four),('자동 실행과 작업 관리','스케줄러와 실행 worker를 분리한다.',five),('Loki 구성 시 결정할 것','라벨·개인정보·보유기간·접근 경로를 명시한다.',six),('프로젝트 구성안 비교','완성 우선 기본안과 운영 관측 추가안을 단계적으로 비교한다.',seven),('다음 검증과 공식 근거','조사에서 확인한 사실과 아직 실행하지 않은 항목.',eight)]
sections=''.join(f'<section id="r{i}"><div class="section-kicker">{i:02d} / FRAMEWORK RESEARCH</div><h2>{t}</h2><p class="lead">{d}</p>{b}</section>' for i,(t,d,b) in enumerate(parts,1))
nav=''.join(f'<a href="#r{i}">{i:02d} {t}</a>' for i,(t,_,_) in enumerate(parts,1))
html=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>맛집 MVP · 크롤링·로그 프레임워크 사전조사</title><style>{css}</style></head><body><div class="shell"><aside class="sidebar"><div class="brand">크롤링 · 로그<small>FRAMEWORK RESEARCH</small></div><nav aria-label="목차">{nav}</nav><div class="side-note">1차 프로젝트 · 2026.10.29<br>공식 문서 조사 / 설치·실측 전<br>C:\\MLops03\\Pro_1</div><button class="print-button" type="button" onclick="window.print()">인쇄 / PDF 저장</button></aside><main><header class="hero"><div class="hero-kicker">RESTAURANT MVP / TECHNOLOGY STUDY</div><h1>수집 도구는 수집을.<br>활동 기록은 DB에.<br>운영 로그는 Loki로.</h1><p>크롤링 프레임워크와 사용자 활동·운영 로그 도구의 사전조사.<br>1차 프로젝트 범위에서 필요한 역할과 도입 순서를 비교합니다.</p><div class="hero-tags"><span>HTTPX · Beautiful Soup</span><span>PostgreSQL</span><span>Alloy · Loki · Grafana</span></div></header>{sections}<footer class="footer">사전조사 권고안 · 공식 문서 확인일 2026-10-29 · 설치·실제 수집·운영 검증 전 · 이 HTML 파일 하나로 공유 가능</footer></main></div><script>
const researchLinks=[...document.querySelectorAll('.sidebar nav a')];const researchObserver=new IntersectionObserver(items=>items.forEach(x=>{{if(x.isIntersecting)researchLinks.forEach(a=>a.classList.toggle('active',a.hash==='#'+x.target.id));}}),{{rootMargin:'-10% 0px -75% 0px'}});document.querySelectorAll('main section').forEach(x=>researchObserver.observe(x));window.addEventListener('beforeprint',()=>document.querySelectorAll('details').forEach(d=>{{d.dataset.wasopen=d.open?'1':'0';d.open=true;}}));window.addEventListener('afterprint',()=>document.querySelectorAll('details').forEach(d=>{{d.open=d.dataset.wasopen==='1';}}));
</script></body></html>'''
OUT.write_text(html,encoding='utf-8')

# 기존 공유 문서에 조사 결과를 직접 포함해 단일 파일 공유를 유지한다.
old=existing.find(id='s12')
if old:old.decompose()
for link in existing.select('.sidebar nav a[href="#s12"]'):link.decompose()
additional=existing.new_tag('section',id='s12')
label=existing.new_tag('div',attrs={'class':'section-kicker'})
label.string='12 / FRAMEWORK RESEARCH · 2026.10.29'
additional.append(label)
heading=existing.new_tag('h2');heading.string='크롤링·로그 프레임워크 사전조사';additional.append(heading)
for title,desc,content in parts:
    h=existing.new_tag('h3');h.string=title;additional.append(h)
    fragment=BeautifulSoup(content,'html.parser')
    for node in list(fragment.contents):additional.append(node.extract())
existing.select_one('main footer').insert_before(additional)
menu=existing.new_tag('a',href='#s12');menu.string='12 크롤링·로그 사전조사';existing.select_one('.sidebar nav').append(menu)
MAIN.write_text(str(existing),encoding='utf-8')

checks=[]
for file in [OUT,MAIN]:
    text=file.read_text(encoding='utf-8')
    doc=BeautifulSoup(text,'html.parser')
    missing=[a['href'] for a in doc.select('a[href^="#"]') if not doc.find(id=a['href'][1:])]
    relative=[a['href'] for a in doc.select('a[href]') if not a['href'].startswith(('http:','https:','#','data:'))]
    assert not missing and not relative,(missing,relative)
    assert not doc.select('script[src],link[rel="stylesheet"],img[src]')
    assert '@import' not in text
    checks.append({'file':str(file),'bytes':file.stat().st_size,'sections':len(doc.select('main > section')),'diagrams':len(doc.select('.diagram svg')),'relative_dependencies':len(relative)})
(ROOT/'research-verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=True,indent=2))
