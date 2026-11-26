"use client";

import { formatKoreanDate, kstAddDays, weekdayShort } from "../lib/dates";

/**
 * 날짜 선택 + 새로고침 바.
 * today는 부모가 넘긴다. 여기서 오늘을 직접 계산하면
 * 빌드 HTML과 방문 시각이 달라 #418이 난다.
 * today/date가 비어 있으면 서버와 같은 "불러오는 중" 화면만 그린다.
 */
export function ReaderTop({
  date,
  today,
  loading,
  onDateChange,
  onRefresh,
}: {
  date: string;
  today: string;
  loading: boolean;
  onDateChange: (date: string) => void;
  onRefresh: () => void;
}) {
  if (!date || !today) {
    return (
      <>
        <div className="reader-top">
          <div>
            <span className="badge">TODAY</span>
            <h2>불러오는 중…</h2>
          </div>
          <button
            className="refresh"
            disabled
            aria-busy="true"
            aria-label="운세 새로고침"
            title="다시 확인"
          >
            확인 중…
          </button>
        </div>
        <div className="dates" />
      </>
    );
  }

  const days = Array.from({ length: 7 }, (_, index) => kstAddDays(today, -index));

  return (
    <>
      <div className="reader-top">
        <div>
          <span className="badge">{date === today ? "TODAY" : "ARCHIVE"}</span>
          <h2>{formatKoreanDate(date)}</h2>
        </div>
        <button
          className="refresh"
          disabled={loading}
          aria-busy={loading}
          onClick={onRefresh}
          aria-label="운세 새로고침"
          title="다시 확인"
        >
          {loading ? "확인 중…" : "↻ 다시 확인"}
        </button>
      </div>
      <div className="dates">
        {days.map((day, index) => (
          <button
            key={day}
            className={date === day ? "active" : ""}
            aria-pressed={date === day}
            onClick={() => onDateChange(day)}
          >
            <span>
              {index === 0 ? "오늘" : index === 1 ? "어제" : weekdayShort(day)}
            </span>
            <b>{Number(day.slice(-2))}</b>
          </button>
        ))}
        <label className="calendar" title="날짜 선택">
          ▦
          <input
            aria-label="운세 날짜 선택"
            type="date"
            value={date}
            max={today}
            onChange={(event) => {
              const value = event.target.value;
              if (/^\d{4}-\d{2}-\d{2}$/.test(value) && value <= today) {
                onDateChange(value);
              }
            }}
          />
        </label>
      </div>
    </>
  );
}
