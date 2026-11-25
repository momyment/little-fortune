"use client";

import { kstDaysAgo, todayKst, formatKoreanDate, weekdayShort } from "../lib/dates";

/**
 * 날짜 선택 + 새로고침 바. 원본 빌드의 모듈 6693 `Ay`와 동일.
 * 오늘부터 7일치 버튼과 날짜 입력(달력)을 제공한다.
 */
export function ReaderTop({
  date,
  loading,
  onDateChange,
  onRefresh,
}: {
  date: string;
  loading: boolean;
  onDateChange: (date: string) => void;
  onRefresh: () => void;
}) {
  const today = todayKst();
  const days = Array.from({ length: 7 }, (_, index) => kstDaysAgo(index));

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
