import { withBasePath } from "./basePath";
import type { HoroscopeEdition, HoroscopeEditionsResponse } from "./types";

export const HOROSCOPE_EDITIONS_PATH = "/api/v1/horoscope/editions.json";

export function horoscopeEditionsUrl(): string {
  return withBasePath(HOROSCOPE_EDITIONS_PATH);
}

export function parseHoroscopeEditions(body: unknown): HoroscopeEdition[] {
  if (Array.isArray(body)) {
    return body as HoroscopeEdition[];
  }
  if (body && typeof body === "object" && "editions" in body) {
    const payload = body as HoroscopeEditionsResponse;
    if (Array.isArray(payload.editions)) {
      return payload.editions;
    }
  }
  throw new Error("Unexpected horoscope API response");
}
