import { FortuneHeader } from "../components/FortuneHeader";
import { HiddenCookie } from "../components/HiddenCookie";
import HoroscopeReader from "../components/HoroscopeReader";
import type { HoroscopeEdition } from "../lib/types";
import "../cookie.css";

const SOURCE_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/";

/**
 * 별자리 운세 회차 데이터. 빌드 시점에 한 번 가져와 정적 페이지에 박아 넣는다.
 * (데이터 파일 자체는 이 소스 프로젝트에 두지 않는다.)
 *
 * 기본값은 운영 사이트에 배포된 horoscope-editions.json이며,
 * HOROSCOPE_DATA_URL 환경 변수로 다른 URL을 지정할 수 있다.
 * (예: 검증용 스냅샷을 로컬 서버로 띄워 놓고 빌드할 때)
 */
function dataUrl(): string {
  return (
    process.env.HOROSCOPE_DATA_URL ??
    "https://momyment.github.io/little-fortune/horoscope-editions.json"
  );
}

export default async function HoroscopePage() {
  const res = await fetch(dataUrl(), { cache: "force-cache" });
  if (!res.ok) {
    throw new Error(`Failed to load horoscope editions: ${res.status}`);
  }
  const editions = (await res.json()) as HoroscopeEdition[];
  return (
    <>
      <FortuneHeader active="horoscope" />
      <div className="fortune-credit">
        <span className="source">
          <span className="spark">✦</span> 아사히 방송
        </span>
      </div>
      <HoroscopeReader editions={editions} sourceUrl={SOURCE_URL} />
      <HiddenCookie piece="footer" />
    </>
  );
}
