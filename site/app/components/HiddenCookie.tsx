"use client";

import { useState } from "react";
import { HUNT_PIECES, useHunt, type HuntPiece } from "./CookieHunt";

/**
 * 페이지 곳곳에 숨은 쪽지 버튼. 원본 빌드의 모듈 9199 `HiddenCookie`와 동일.
 * 아직 찾지 않은 쪽지일 때만 나타나며, 클릭하면 쪽지가 튀어 오르는
 * 애니메이션 뒤 수집된다. 위치는 날짜(일) + 쪽지 순서로 정해진다.
 */
export function HiddenCookie({ piece }: { piece: HuntPiece }) {
  const hunt = useHunt();
  const [popping, setPopping] = useState(false);

  if (!hunt.progress.date || hunt.progress.found.includes(piece)) {
    return null;
  }

  const position =
    (Number(hunt.progress.date.slice(-2)) + HUNT_PIECES.indexOf(piece)) % 3;

  return (
    <div className="hidden-cookie-row" data-position={position}>
      <button
        type="button"
        className={popping ? "hidden-cookie is-popping" : "hidden-cookie"}
        aria-label="숨은 쪽지 줍기"
        aria-disabled={popping}
        onClick={() => {
          if (popping) return;
          if (
            window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ) {
            hunt.collect(piece);
          } else {
            setPopping(true);
          }
        }}
        onAnimationEnd={() => {
          if (popping) {
            setPopping(false);
            hunt.collect(piece);
          }
        }}
      >
        <span className="cookie-folded-note" aria-hidden="true" />
      </button>
    </div>
  );
}
