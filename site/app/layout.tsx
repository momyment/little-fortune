import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "오늘의 작은 운세",
  description: "하루를 가볍게 여는 신비사주 띠별 운세",
};

/**
 * 루트 레이아웃. 원본 빌드의 RSC 트리와 동일:
 * 헤더, main(본문 + 마무리 문구 + 푸터)을 렌더링한다.
 * 각 페이지가 인트로/탭 내비게이션과 운세 리더를 main 안에 넣는다.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body
        style={
          {
            "--folded-note": 'url("/little-fortune/folded-note.png")',
          } as React.CSSProperties
        }
      >
        <header>
          <a className="brand" href="/little-fortune/">
            ✳ <span>오늘의 작은 운세</span>
          </a>
          <span className="edition">DAILY FORTUNE</span>
        </header>
        <main>
          {children}
          <aside>
            <span aria-hidden="true">✧</span>
            <p>
              좋은 말은 마음에 담고,
              <br />
              걱정되는 말은 가볍게 흘려보내세요.
            </p>
          </aside>
          <footer>
            <span>오늘의 작은 운세</span>
            <p>
              별자리 운세 출처 ·{" "}
              <a
                href="https://www.asahi.co.jp/ohaasa/week/horoscope/"
                target="_blank"
                rel="noreferrer"
              >
                아사히 방송
              </a>
              <br />
              날짜는 한국 시간을 기준으로 표시해요.
            </p>
            <small>FOR A LITTLE BRIGHTER DAY</small>
          </footer>
        </main>
      </body>
    </html>
  );
}
