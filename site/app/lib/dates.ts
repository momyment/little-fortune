// 한국 시간(Asia/Seoul) 날짜 유틸. 원본 빌드의 모듈 6693과 동일.
const seoulFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
});

/** 오늘 날짜 (YYYY-MM-DD, 한국 시간 기준). */
export function todayKst(): string {
  return seoulFormat.format(new Date());
}

/** 오늘로부터 days일 전 날짜 (YYYY-MM-DD, 한국 시간 기준). */
export function kstDaysAgo(days: number): string {
  const today = todayKst();
  return seoulFormat.format(
    new Date(new Date(`${today}T12:00:00+09:00`).getTime() - 86400000 * days),
  );
}

/** "2026-11-24" -> "11월 24일 화요일" */
export function formatKoreanDate(date: string): string {
  return new Date(`${date}T12:00:00+09:00`).toLocaleDateString("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "long",
    timeZone: "Asia/Seoul",
  });
}

/** "2026-11-24" -> "월" (짧은 요일) */
export function weekdayShort(date: string): string {
  return new Date(`${date}T12:00:00+09:00`).toLocaleDateString("ko-KR", {
    weekday: "short",
    timeZone: "Asia/Seoul",
  });
}
