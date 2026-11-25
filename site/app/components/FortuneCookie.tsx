"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { COOKIE_MESSAGES } from "../lib/cookieMessages";
import { withBasePath } from "../lib/basePath";

const SESSION_KEY = "little-fortune-cookie-session";

/**
 * 포춘쿠키 뽑기 패널 + 다이얼로그. 원본 빌드의 모듈 2621 `g`와 동일.
 * - 뽑은 메시지는 세션 동안 sessionStorage에 저장돼 새로고침해도 유지되고,
 *   다음 날이면 다시 뽑을 수 있다.
 * - 쿠키가 터지는 애니메이션이 끝나면 다이얼로그가 열린다.
 * - `prefers-reduced-motion`이면 애니메이션 없이 바로 다이얼로그를 연다.
 */
export function FortuneCookie() {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const [message, setMessage] = useState("");
  const [bursting, setBursting] = useState(false);
  const [drawn, setDrawn] = useState(false);
  const drawnMessage = drawn ? message : "";

  function openWith(nextMessage: string = message) {
    try {
      sessionStorage.setItem(SESSION_KEY, nextMessage);
    } catch {}
    setBursting(false);
    setDrawn(true);
    dialogRef.current?.showModal();
  }

  useLayoutEffect(() => {
    function readSession() {
      try {
        const saved = sessionStorage.getItem(SESSION_KEY) ?? "";
        setMessage(saved);
        setDrawn(!!saved);
      } catch {}
    }
    const navigation = performance.getEntriesByType(
      "navigation",
    )[0] as PerformanceNavigationTiming | undefined;
    if (navigation?.type === "reload") {
      try {
        sessionStorage.removeItem(SESSION_KEY);
      } catch {}
    }
    function onPageShow(event: PageTransitionEvent) {
      if (event.persisted) readSession();
    }
    readSession();
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, []);

  return (
    <>
      <div className="cookie-panel">
        <button
          type="button"
          className="cookie-trigger"
          onClick={() => {
            if (bursting || drawn) return;
            const picked =
              COOKIE_MESSAGES[Math.floor(Math.random() * COOKIE_MESSAGES.length)];
            setMessage(picked);
            if (
              window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ) {
              openWith(picked);
            } else {
              setBursting(true);
            }
          }}
          aria-haspopup={drawnMessage ? undefined : "dialog"}
          disabled={!!drawnMessage}
          aria-disabled={bursting || !!drawnMessage}
        >
          <span className="cookie-emoji" aria-hidden="true">
            <span className={bursting ? "cookie-intact" : undefined}>🥠</span>
            {bursting && (
              <span
                className="cookie-burst"
                onAnimationEnd={(event) => {
                  if (event.target === event.currentTarget) openWith();
                }}
              >
                <span className="cookie-fragment cookie-fragment-left">
                  🥠
                </span>
                <span className="cookie-fragment cookie-fragment-right">
                  🥠
                </span>
              </span>
            )}
          </span>
          <span className="cookie-bubble">
            {drawnMessage ? "내일 다시 만나요 :)" : "오늘의 포춘쿠키 뽑기"}
          </span>
        </button>
        {drawnMessage && (
          <p className="cookie-drawn fortune-result">{drawnMessage}</p>
        )}
      </div>
      <dialog
        ref={dialogRef}
        className="cookie-dialog"
        aria-labelledby="cookie-title"
      >
        <form method="dialog">
          <button
            className="cookie-close"
            aria-label="포춘쿠키 닫기"
            autoFocus
          >
            ×
          </button>
        </form>
        <div className="cookie-crack" aria-hidden="true">
          <img
            src={withBasePath("/fortune-cookie-open.png")}
            alt=""
            width={497}
            height={247}
          />
        </div>
        <h2 id="cookie-title">오늘의 포춘쿠키</h2>
        <p className="cookie-message">{message}</p>
      </dialog>
    </>
  );
}
