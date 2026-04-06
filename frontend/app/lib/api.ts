const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types (mirror backend Pydantic schemas)
// ---------------------------------------------------------------------------

export interface County {
  fips_code: string;
  name: string;
  population: number | null;
  centroid_lat: number | null;
  centroid_lng: number | null;
}

export interface Disease {
  id: number;
  name: string;
  category: string | null;
  icd10_code: string | null;
  herd_threshold_pct: number | null;
  r0_estimate: number | null;
}

export interface CaseSummary {
  county_fips: string;
  total_cases: number;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export function fetchCounties(): Promise<County[]> {
  return get<County[]>("/counties/");
}

export function fetchDiseases(): Promise<Disease[]> {
  return get<Disease[]>("/diseases/");
}

export function fetchCasesSummary(params: {
  disease_id?: number;
  date_from?: string;
  date_to?: string;
}): Promise<CaseSummary[]> {
  const qs = new URLSearchParams();
  if (params.disease_id !== undefined)
    qs.set("disease_id", String(params.disease_id));
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  const query = qs.toString() ? `?${qs}` : "";
  return get<CaseSummary[]>(`/cases/summary${query}`);
}
