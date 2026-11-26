export interface HoroscopeEntry {
  rank: number;
  sign: string;
  summary: string;
  lucky?: string;
  ja_summary?: string;
  ja_lucky?: string;
}

export interface HoroscopeEdition {
  date: string;
  entries: HoroscopeEntry[];
}

export interface HoroscopeEditionsResponse {
  ok: boolean;
  version: number;
  type: "horoscope-editions";
  updated_at: string;
  dates: string[];
  editions: HoroscopeEdition[];
}

export interface HoroscopeEditionResponse {
  ok: boolean;
  version: number;
  type: "horoscope-edition";
  updated_at: string;
  date: string;
  edition: HoroscopeEdition;
}

export interface FortuneItem {
  shortcode: string;
  image: string;
  source: string;
}

export interface FortuneIndexResponse {
  ok: boolean;
  version: number;
  type: "fortune-index";
  updated_at: string;
  dates: string[];
  fortunes: Record<string, FortuneItem>;
}
