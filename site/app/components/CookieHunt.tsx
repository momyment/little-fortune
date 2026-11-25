"use client";

import { useEffect, useState } from "react";
import { BONUS_SONGS } from "../lib/songs";
import { todayKst } from "../lib/dates";

const STORAGE_KEY = "little-fortune-cookie-hunt-v2";
const PROGRESS_EVENT = "fortune-note-progress";

export const HUNT_PIECES = ["zodiac", "horoscope", "footer"] as const;
export type HuntPiece = (typeof HUNT_PIECES)[number];

const HINTS: Record<HuntPiece, string> = {
  zodiac: "띠별 운세에서 사진 아래쪽을 살펴보세요.",
  horoscope: "별자리 순위표 위쪽 여백을 살펴보세요.",
  footer: "페이지 아래의 마무리 문구 근처를 살펴보세요.",
};

export interface HuntProgress {
  date: string;
  found: HuntPiece[];
}

// 다른 탭/컴포넌트와 진행 상황을 맞추기 위한 모듈 단위 캐시.
let cachedProgress: HuntProgress | undefined;

function readProgress(date: string): HuntProgress {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    if (parsed?.date === date && Array.isArray(parsed.found)) {
      return {
        date,
        found: HUNT_PIECES.filter((piece) => parsed.found.includes(piece)),
      };
    }
  } catch {}
  return { date, found: [] };
}

/**
 * 숨은 쪽지 수집 진행 상황 훅. 원본 빌드의 모듈 9199 `u`와 동일.
 * 자정이 지나면 날짜가 바뀌어 진행 상황이 초기화된다.
 */
export function useHunt() {
  const [progress, setProgress] = useState<HuntProgress>({
    date: "",
    found: [],
  });

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    function refresh() {
      clearTimeout(timer);
      const today = todayKst();
      const stored = readProgress(today);
      setProgress(
        stored.found.length === 0 && cachedProgress?.date === today
          ? cachedProgress
          : stored,
      );
      timer = setTimeout(
        refresh,
        Math.max(
          1,
          Date.parse(`${today}T00:00:00+09:00`) + 86400000 - Date.now(),
        ),
      );
    }
    refresh();
    window.addEventListener(PROGRESS_EVENT, refresh);
    window.addEventListener("storage", refresh);
    window.addEventListener("pageshow", refresh);
    return () => {
      clearTimeout(timer);
      window.removeEventListener(PROGRESS_EVENT, refresh);
      window.removeEventListener("storage", refresh);
      window.removeEventListener("pageshow", refresh);
    };
  }, []);

  return {
    progress,
    collect(piece: HuntPiece) {
      const today = todayKst();
      const stored = readProgress(today);
      const found = HUNT_PIECES.filter(
        (p) =>
          p === piece ||
          stored.found.includes(p) ||
          (progress.date === today && progress.found.includes(p)),
      );
      const next = { date: today, found };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {}
      cachedProgress = next;
      window.dispatchEvent(new Event(PROGRESS_EVENT));
    },
  };
}

/**
 * 숨은 쪽지 찾기 패널. 원본 빌드의 모듈 9199 `h`와 동일.
 * 3곳을 모두 찾으면 오늘의 한 곡(보너스 쪽지)이 펼쳐진다.
 */
export function CookieHunt() {
  const hunt = useHunt();
  const [expanded, setExpanded] = useState("");
  const { date, found } = hunt.progress;
  const nextPiece = HUNT_PIECES.find((piece) => !found.includes(piece));
  const foundCount = found.length;
  const bonus =
    BONUS_SONGS[(Math.floor(Date.parse(date) / 86400000) || 0) % BONUS_SONGS.length];
  const showHint = !nextPiece || expanded === date + foundCount;

  return (
    <div className="cookie-hunt">
      <button
        type="button"
        className="cookie-trigger note-trigger"
        disabled={!nextPiece}
        aria-expanded={nextPiece ? showHint : undefined}
        onClick={() => setExpanded(showHint ? "" : date + foundCount)}
      >
        <span className="cookie-bubble">
          {nextPiece
            ? `숨은 쪽지 찾기 ${foundCount}/3`
            : "내일 또 찾아보세요"}
        </span>
        <span className="cookie-folded-note" aria-hidden="true" />
      </button>
      <span className="cookie-hunt-status" role="status">
        찾은 쪽지 {foundCount}/3
      </span>
      {showHint &&
        (nextPiece ? (
          <p>{HINTS[nextPiece]}</p>
        ) : (
          <div className="cookie-bonus-paper fortune-result">
            <span>{bonus.message}</span>
            <small className="bonus-track">
              <span className="bonus-track-label">♫ 오늘의 한 곡</span>
              <span>
                {bonus.artist}{" "}
                <span className="bonus-track-title">〈{bonus.song}〉</span>
              </span>
            </small>
          </div>
        ))}
    </div>
  );
}
