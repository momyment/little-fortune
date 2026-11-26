import { FortuneHeader } from "../components/FortuneHeader";
import { HiddenCookie } from "../components/HiddenCookie";
import HoroscopeReader from "../components/HoroscopeReader";
import "../cookie.css";

const SOURCE_URL = "https://www.asahi.co.jp/ohaasa/week/horoscope/";

/**
 * 별자리 운세 페이지. 날짜와 회차는 빌드에 박지 않는다.
 * 브라우저가 /api/v1/horoscope/editions.json 을 런타임에 가져온다.
 */
export default function HoroscopePage() {
  return (
    <>
      <FortuneHeader active="horoscope" />
      <div className="fortune-credit">
        <span className="source">
          <span className="spark">✦</span> 아사히 방송
        </span>
      </div>
      <HoroscopeReader sourceUrl={SOURCE_URL} />
      <HiddenCookie piece="footer" />
    </>
  );
}
