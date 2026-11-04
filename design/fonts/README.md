# design/fonts — 글꼴 후보 5종

공간큐브 화면에 쓸 한글 글꼴 후보입니다. 다섯 가지 모두 SIL Open Font License 1.1(OFL)이라 상업적으로 써도 되고, 글꼴 파일만 따로 팔 수는 없습니다. 디자인 캔버스 '글꼴 시안' 페이지에서 같은 화면 조각으로 비교할 수 있습니다.

| 글꼴 | 버전 | 굵기 | 가변 | 원본 크기 | 웹용 woff2 (서브셋) | 출처 |
| --- | --- | --- | --- | --- | --- | --- |
| Noto Sans KR | Google Fonts 최신 | 100~900 | 있음 | 10.2MB | 324KB | [google/fonts](https://github.com/google/fonts/tree/main/ofl/notosanskr) |
| Pretendard | 1.3.9 | 9종 (Thin~Black) | 있음 | 6.6MB (가변) | 474KB | [orioncactus/pretendard](https://github.com/orioncactus/pretendard) |
| Freesentation | 2.001 | 9종 (Thin~Black) | 있음 | 6.8MB (가변) | 407KB | [Freesentation](https://freesentation.blog/freesentation) |
| SUIT Variable | 최신 릴리스 | 100~900 | 있음 | 1.5MB | 513KB | [sun-typeface/SUIT](https://github.com/sun-typeface/SUIT) |
| Spoqa Han Sans Neo | 3.3.0 | 5종 (Thin·Light·Regular·Medium·Bold) | 없음 | 굵기당 약 13MB | 굵기당 약 156KB (Regular·Medium·Bold 3개) | [spoqa/spoqa-han-sans](https://github.com/spoqa/spoqa-han-sans) |

## 폴더

- `<글꼴>/original/`: 공식 배포 원본(TTF)과 라이선스 파일. Freesentation은 zip에 라이선스 문서가 없어 `LICENSE-NOTE.md`로 공식 안내를 옮겨 둠
- `make_webfonts.py`: 원본 → 웹용 서브셋 woff2. 쓰는 글꼴(Noto Sans KR)은 `frontend/public/fonts/`, 비교용 후보 4종은 `design/fonts/web/`(배포에 안 들어감)

## 웹용 서브셋 만들기

```bash
conda activate pro_1
python design/fonts/make_webfonts.py
```

KS X 1001 한글 2,350자, 영문·숫자·기본 기호, 한글 자모, ₩·★·①~⑳ 같은 기호만 남깁니다. 이 범위 밖 글자(예: 똠, 햏)는 브라우저가 다음 글꼴(시스템 글꼴)로 대신 그립니다. 사용자 이름처럼 드문 글자가 꼭 필요하면 범위를 넓혀 다시 만듭니다.

## 이 PC 설치 상태 (2026-11-01)

| 글꼴 | 설치 위치 |
| --- | --- |
| Noto Sans KR (가변), Pretendard Regular~ExtraBold | 이미 시스템에 있음 (`C:\Windows\Fonts`) |
| Pretendard Thin·ExtraLight·Black·Variable, Freesentation 9종, SUIT Variable, Spoqa Han Sans Neo 5종 | 내 계정 글꼴로 추가 설치 (`%LOCALAPPDATA%\Microsoft\Windows\Fonts`) |

이미 열려 있던 프로그램은 다시 켜야 새 글꼴이 목록에 보일 수 있습니다.
