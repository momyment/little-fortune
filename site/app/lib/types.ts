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
