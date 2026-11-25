"use client";

import { useLayoutEffect } from "react";
import { FortuneCookie } from "./FortuneCookie";
import { CookieHunt } from "./CookieHunt";
import { withBasePath } from "../lib/basePath";

const SCROLL_KEY = "fortune-tab-scroll";

/**
 * 운세 종류 탭을 눌렀을 때 스크롤 위치를 저장한다. 원본 빌드의 모듈 2621 `m`과 동일.
 * 같은 탭을 다시 누르면 이동하지 않는다.
 */
function saveScrollOnNav(event: React.MouseEvent<HTMLAnchorElement>) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }
  const destination = event.currentTarget.pathname;
  if (destination === location.pathname) {
    event.preventDefault();
    return;
  }
  try {
    sessionStorage.setItem(
      SCROLL_KEY,
      JSON.stringify({ destination, top: window.scrollY }),
    );
  } catch {}
}

/**
 * 인트로 + 운세 종류 내비게이션. 원본 빌드의 모듈 2621 기본 내보내기와 동일.
 * 탭을 이동한 뒤 돌아오면 저장해 둔 스크롤 위치로 복원한다.
 */
export function FortuneHeader({
  active,
}: {
  active: "zodiac" | "horoscope";
}) {
  useLayoutEffect(() => {
    try {
      const saved = sessionStorage.getItem(SCROLL_KEY);
      if (!saved) return;
      sessionStorage.removeItem(SCROLL_KEY);
      const { destination, top } = JSON.parse(saved);
      if (destination === location.pathname && Number.isFinite(top)) {
        window.scrollTo({ top, behavior: "instant" as ScrollBehavior });
      }
    } catch {}
  }, []);

  return (
    <>
      <section className="intro">
        <span className="eyebrow">하루를 여는 작은 습관</span>
        <h1>
          오늘은 어떤 하루가
          <br />
          기다리고 있을까요<span>?</span>
        </h1>
        <p>운세 한 장, 가벼운 마음으로 시작하는 오늘.</p>
        <div className="fortune-activities">
          <FortuneCookie />
          <CookieHunt />
        </div>
      </section>
      <nav className="fortune-nav" aria-label="운세 종류">
        <a
          href={withBasePath("/")}
          onClick={saveScrollOnNav}
          aria-current={active === "zodiac" ? "page" : undefined}
        >
          띠별 운세
        </a>
        <a
          href={withBasePath("/horoscope/")}
          onClick={saveScrollOnNav}
          aria-current={active === "horoscope" ? "page" : undefined}
        >
          별자리 운세
        </a>
      </nav>
    </>
  );
}
