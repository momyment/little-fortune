# little-fortune — 별자리 운세 페이지 소스 재구성

`momyment/little-fortune` 저장소에는 빌드 결과물만 있고 소스가 없어,
배포된 페이지(https://momyment.github.io/little-fortune/horoscope/)를
역공학해 Next.js 소스를 재구성한 프로젝트다.
디자인·기능은 일절 바꾸지 않았다. 대상은 별자리 운세 페이지와
공유 레이아웃/스타일이며, 메인 인덱스 페이지는 범위 밖이다.

## 스택

- Next.js 15.5.29 (App Router, `output: "export"`, `basePath: "/little-fortune"`, `trailingSlash: true`)
- React 19.3.0, TypeScript
- 빌드 결과물: `out/horoscope/index.html` 등 정적 파일

## 날짜 콘텐츠가 페이지에 들어가는 방식 (중요)

페이지가 날짜별 운세를 얻는 경로는 두 가지이며, 이 소스는 둘 다 원본 그대로 유지한다.

1. **빌드 시점에 정적 HTML에 박힌다 (주 경로).**
   `app/horoscope/page.tsx`(서버 컴포넌트)가 빌드할 때
   `horoscope-editions.json` 전체를 가져와 `HoroscopeReader`에 props로 넘긴다.
   초기 날짜, 7일 버튼, TODAY 배지, 순위 목록이 모두 빌드 시점 데이터로
   서버 렌더링된다. 그래서 데이터 커밋만으로는 배포된 페이지가 안 바뀌고
   **새 빌드 + 배포가 있어야** 새 날짜가 반영된다.
   빌드 시 데이터 URL은 `HOROSCOPE_DATA_URL` 환경 변수로 지정한다.
   기본값은 운영 사이트의 `https://momyment.github.io/little-fortune/horoscope-editions.json`.
   데이터 파일 자체는 이 소스 프로젝트에 두지 않는다.
2. **런타임에는 "↻ 다시 확인" 버튼만 다시 가져온다.**
   `HoroscopeReader`의 새로고침 버튼이 `fetch("/little-fortune/horoscope-editions.json", {cache:"no-store"})`로
   최신 데이터를 받아 state를 교체한다. 마운트 시 자동 fetch는 없다.
   실패 시 "연결이 잠시 끊겼어요. 다시 확인해 주세요."를 보여준다.

주말에는 해당 날짜 데이터가 없으므로
"주말에는 별자리 운세도 잠시 쉬어가요" / "새로운 별자리 운세는 평일에 만나요."가
나오고, 평일인데 데이터가 없으면
"이 날짜에 게시된 한국어 별자리 운세가 없어요"가 나온다.

## 로컬 빌드

```bash
cd site
npm install
npm run build        # out/ 에 정적 파일 생성
npx serve out        # 또는 python3 -m http.server --directory out
```

빌드 시점 데이터는 `HOROSCOPE_DATA_URL`로 바꿀 수 있다.
(검증할 때는 특정 날짜 스냅샷을 로컬 서버로 띄워 놓고 그 URL을 지정했다.)

## 자동 배포 (GitHub Actions)

워크플로 파일: `.github/workflows/deploy.yml`
(저장소 루트에 둔다. 소스 프로젝트는 저장소 루트의 `site/`에 있다고 가정한다.)

- main에 푸시될 때마다 빌드 → GitHub Pages 배포.
- 빌드 시 이번 커밋의 `horoscope-editions.json`을
  `raw.githubusercontent.com/.../<sha>/horoscope-editions.json`에서 가져와
  해당 커밋의 데이터를 정확히 박아 넣는다.
  (라이브 사이트 JSON을 쓰면 배포 전 페이지가 어제 날짜인 동안의 레이스가 생긴다.)
- 빌드 후 배포물을 조립한다: 새 빌드(`site/out/`)만으로는 별자리 페이지만
  나오므로, 루트의 정적 파일(메인 인덱스 `index.html`, `fortunes/`,
  데이터 JSON, favicon, `.nojekyll`)과 구 빌드의 `_next/`(인덱스 페이지의
  JS/CSS 청크)를 합친다. `horoscope/`는 새 빌드로 대체한다.
  인덱스 페이지 소스가 아직 없어서, 인덱스 페이지와 그 청크는
  당분간 루트의 빌드 결과물을 그대로 쓴다. 인덱스 소스가 재구성되면
  이 합치기 단계는 사라진다.

**필요한 저장소 설정 1가지:**
Pages → Build and deployment → Source를 **GitHub Actions**로 바꾼다.
(지금은 "Deploy from a branch"일 것이다. 바꾸지 않으면 이 워크플로가
배포하지 않고 루트의 낡은 빌드 결과물이 계속 서빙된다.)

**대안 (설정 변경 없음):**
빌드한 `out/` 내용을 다시 main에 커밋해 기존 "Deploy from a branch" 방식을
유지하는 방법도 있다. 하지만 매 데이터 커밋마다 빌드 결과물 커밋이
추가돼 히스토리가 오염되고, 커밋이 다시 워크플로를 트리거하는
루프를 막는 가드가 필요해진다. **권장: GitHub Actions 소스 방식.**
전환 후에도 루트 파일 중 인덱스 페이지(`index.html`, `_next/` 청크,
`fortunes/`, 데이터 JSON)는 계속 쓰인다. 안 쓰게 되는 건 구 `horoscope/`
빌드 결과물과 `__next.*.txt`뿐이라, 정리 여부는 별도로 검토한다.

## 프로젝트 구조

```
site/
  package.json / next.config.ts / tsconfig.json
  app/
    layout.tsx          # 루트 레이아웃: 헤더, main, 마무리 문구, 푸터
    globals.css         # 전역 스타일 (원본 CSS 그대로)
    cookie.css          # 포춘쿠키/쪽지 사냥 스타일 (원본 CSS 그대로)
    horoscope/page.tsx  # 서버 컴포넌트: 빌드 시 데이터 fetch + 페이지 조립
    components/
      HoroscopeReader.tsx  # 별자리 리더 (날짜 이동, 생일 필터, 순위, 새로고침)
      FortuneHeader.tsx    # 인트로 + 탭 내비게이션 + 포춘쿠키
      FortuneCookie.tsx    # 포춘쿠키 다이얼로그 (메시지 100개)
      CookieHunt.tsx       # 숨은 쪽지 사냥 (쪽지 3개, 노래 100곡)
      HiddenCookie.tsx     # 숨은 쪽지 조각
      ReaderTop.tsx        # TODAY/ARCHIVE 배지, 새로고침 버튼, 7일 날짜 버튼
    lib/
      basePath.ts dates.ts types.ts
      cookieMessages.ts   # 포춘쿠키 메시지 100개 (원본 그대로)
      songs.ts            # 오늘의 노래 100곡 (원본 그대로)
      signIcons.ts        # 12별자리 아이콘/톤
  public/
    fortune-cookie-open.png  # 루트 파일로의 심볼릭 링크 (원본과 바이트 동일)
    folded-note.png          # 루트 파일로의 심볼릭 링크 (원본과 바이트 동일)
  REPORT.md                  # 원본 페이지와의 검증 결과
```
워크플로 파일은 저장소 루트의 `.github/workflows/deploy.yml`에 둔다
(site/ 안이 아니다).

자세한 검증 결과는 `REPORT.md`를 본다.
