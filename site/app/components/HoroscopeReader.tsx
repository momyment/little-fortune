"use client";

import { useEffect, useState } from "react";
import { ReaderTop } from "./ReaderTop";
import { HiddenCookie } from "./HiddenCookie";
import { SIGN_ICONS } from "../lib/signIcons";
import { todayKst } from "../lib/dates";
import { horoscopeEditionsUrl, parseHoroscopeEditions } from "../lib/api";
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
 * 별자리 운세 리더. 날짜와 회차는 빌드에 박지 않는다.
 * 첫 화면은 서버/클라이언트가 같은 "불러오는 중" 상태라 #418이 나지 않고,
 * 마운트 뒤에 오늘(KST)을 고르고 /api/v1/horoscope/editions.json 을 가져온다.
 */
export default function HoroscopeReader({ sourceUrl }: { sourceUrl: string }) {
  const [allEditions, setAllEditions] = useState<HoroscopeEdition[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [date, setDate] = useState("");
  const [today, setToday] = useState("");
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
  const dayOfWeek = date ? new Date(`${date}T00:00:00Z`).getUTCDay() : -1;
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
  const edition = allEditions.find((entry) => entry.date === date);
  const entries = edition?.entries.filter(
    (entry) => !signFilter || entry.sign === signFilter,
  );
  const ready = Boolean(date && today);

  async function refresh() {
    setLoading(true);
    setLoadError(false);
    try {
      const res = await fetch(horoscopeEditionsUrl(), { cache: "no-store" });
      if (!res.ok) throw new Error("Refresh failed");
      setAllEditions(parseHoroscopeEditions(await res.json()));
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const current = todayKst();
    setToday(current);
    setDate(current);
    void refresh();
    // 마운트 때 한 번만. 오늘 날짜는 여기서만 정해서 첫 HTML과 어긋나지 않게 한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="reader">
      <ReaderTop
        date={date}
        today={today}
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
      {!ready ? (
        <div className="paper">
          <div className="empty">
            <span className="orb">☁</span>
            <h3>불러오는 중…</h3>
            <p>오늘의 별자리 운세를 확인하고 있어요.</p>
          </div>
        </div>
      ) : edition ? (
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
