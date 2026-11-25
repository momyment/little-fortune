"use client";

import { useState } from "react";
import { ReaderTop } from "./ReaderTop";
import { HiddenCookie } from "./HiddenCookie";
import { SIGN_ICONS } from "../lib/signIcons";
import { todayKst } from "../lib/dates";
import { withBasePath } from "../lib/basePath";
import type { HoroscopeEdition } from "../lib/types";

const SIGNS = [
  "염소자리",
  "물병자리",
  "물고기자리",
  "양자리",
  "황소자리",
  "쌍둥이자리",
  "게자리",
  "사자자리",
  "처녀자리",
  "천칭자리",
  "전갈자리",
  "사수자리",
];
const CUSP_DAYS = [20, 19, 21, 20, 21, 22, 23, 23, 23, 23, 22, 22];
const DAYS_IN_MONTH = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function SignIcon({ sign }: { sign: string }) {
  const found = SIGN_ICONS[sign];
  if (!found) return null;
  const [path, tone] = found;
  return (
    <span className="sign-icon" data-tone={tone} aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        focusable="false"
      >
        <path d={path} />
      </svg>
    </span>
  );
}

/**
 * 별자리 운세 리더. 원본 빌드의 `app/horoscope/page-*.js` 모듈 3272와 동일.
 * - 날짜를 고르면 해당 날짜의 회차를 보여준다. (주말에는 회차가 없어 빈 상태)
 * - 생일(월/일)을 넣으면 별자리를 계산해 해당 별자리만 걸러서 보여준다.
 * - "다시 확인"은 horoscope-editions.json을 새로 받아온다 (cache: no-store).
 */
export default function HoroscopeReader({
  editions,
  sourceUrl,
}: {
  editions: HoroscopeEdition[];
  sourceUrl: string;
}) {
  const [allEditions, setAllEditions] = useState(editions);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [date, setDate] = useState(todayKst);
  const [birthMonth, setBirthMonth] = useState("");
  const [birthDay, setBirthDay] = useState("");
  const [signFilter, setSignFilter] = useState("");

  const month = Number(birthMonth);
  const day = Number(birthDay);
  const birthdayValid =
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    day <= DAYS_IN_MONTH[month - 1];
  const dayOfWeek = new Date(`${date}T00:00:00Z`).getUTCDay();
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
  const edition = allEditions.find((entry) => entry.date === date);
  const entries = edition?.entries.filter(
    (entry) => !signFilter || entry.sign === signFilter,
  );

  async function refresh() {
    setLoading(true);
    setLoadError(false);
    try {
      const res = await fetch(withBasePath("/horoscope-editions.json"), {
        cache: "no-store",
      });
      if (!res.ok) throw new Error("Refresh failed");
      setAllEditions(await res.json());
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="reader">
      <ReaderTop
        date={date}
        loading={loading}
        onDateChange={setDate}
        onRefresh={refresh}
      />
      {loadError && (
        <p role="status" className="check-status">
          연결이 잠시 끊겼어요. 다시 확인해 주세요.
        </p>
      )}
      <form
        className="zodiac-form birthday-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (birthdayValid) {
            setSignFilter(
              SIGNS[(month - Number(day < CUSP_DAYS[month - 1])) % SIGNS.length],
            );
          }
        }}
      >
        <label htmlFor="birth-month">생일로 내 별자리 보기</label>
        <div>
          <input
            id="birth-month"
            aria-label="태어난 월"
            inputMode="numeric"
            placeholder="월"
            maxLength={2}
            value={birthMonth}
            onChange={(event) =>
              setBirthMonth(event.target.value.replace(/\D/g, ""))
            }
          />
          <input
            aria-label="태어난 일"
            inputMode="numeric"
            placeholder="일"
            maxLength={2}
            value={birthDay}
            onChange={(event) =>
              setBirthDay(event.target.value.replace(/\D/g, ""))
            }
          />
          <button type="submit" disabled={!birthdayValid}>
            내 별자리 보기
          </button>
          {signFilter && (
            <button type="button" onClick={() => setSignFilter("")}>
              전체 보기
            </button>
          )}
        </div>
        {signFilter && <small>{signFilter} 운세</small>}
      </form>
      <HiddenCookie piece="horoscope" />
      {edition ? (
        <>
          <p className="check-status">한국어 번역</p>
          <ol className="asahi-ranking">
            {entries?.map((entry) => (
              <li key={entry.sign}>
                <span className="asahi-rank">{entry.rank}위</span>
                <div>
                  <h3 className="asahi-sign">
                    <SignIcon sign={entry.sign} />
                    {entry.sign}
                  </h3>
                  <p>{entry.summary}</p>
                  {entry.lucky && (
                    <small>
                      행운 아이템 <span>{entry.lucky}</span>
                    </small>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <div className="paper">
          <div className="empty">
            <span className="orb">☁</span>
            <h3>
              {isWeekend
                ? "주말에는 별자리 운세도 잠시 쉬어가요"
                : "이 날짜에 게시된 한국어 별자리 운세가 없어요"}
            </h3>
            <p>
              {isWeekend
                ? "새로운 별자리 운세는 평일에 만나요."
                : "번역이 올라오면 이곳에서 볼 수 있어요."}
            </p>
          </div>
        </div>
      )}
      <div className="reader-foot">
        <span>✦ 아사히 별자리 운세</span>
        <a href={sourceUrl} target="_blank" rel="noreferrer">
          아사히 방송 원문 보기 ↗
        </a>
      </div>
    </section>
  );
}
