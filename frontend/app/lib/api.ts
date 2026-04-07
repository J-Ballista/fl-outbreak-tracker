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
  confirmed_total: number;
  probable_total: number;
}

export interface VaccinationSummary {
  county_fips: string;
  vaccinated_pct: number;
  exempt_medical_pct: number | null;
  exempt_religious_pct: number | null;
  survey_year: number;
}

export interface CountyDiseaseVaccRate {
  disease_id: number;
  vaccinated_pct: number;
  survey_year: number;
}

export interface NewsSignal {
  id: number;
  county_fips: string | null;
  disease_id: number | null;
  extracted_case_count: number | null;
  confidence: number | null;
  article_id: number;
  article_title: string | null;
  article_url: string;
  article_source: string | null;
  article_published_at: string | null;
}

export interface Alert {
  id: number;
  county_fips: string;
  disease_id: number;
  alert_date: string;
  severity: "watch" | "warning" | "emergency";
  metric: string;
  threshold_value: number | null;
  observed_value: number | null;
  resolved_at: string | null;
  created_at: string;
}

export interface TrendPoint {
  report_date: string;
  total_cases: number;
}

export interface AgeBreakdownRow {
  age_group: string;
  total_cases: number;
}

export interface AcquisitionBreakdownRow {
  acquisition: string;
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

export function fetchVaccinationSummary(params: {
  disease_id?: number;
  survey_year?: number;
}): Promise<VaccinationSummary[]> {
  const qs = new URLSearchParams();
  if (params.disease_id !== undefined)
    qs.set("disease_id", String(params.disease_id));
  if (params.survey_year !== undefined)
    qs.set("survey_year", String(params.survey_year));
  const query = qs.toString() ? `?${qs}` : "";
  return get<VaccinationSummary[]>(`/vaccination-rates/summary${query}`);
}

export function fetchCountyVaccRates(fips_code: string, survey_year?: number): Promise<CountyDiseaseVaccRate[]> {
  const qs = survey_year !== undefined ? `?survey_year=${survey_year}` : "";
  return get<CountyDiseaseVaccRate[]>(`/vaccination-rates/county/${fips_code}${qs}`);
}

export function fetchNewsSignals(params: {
  county_fips?: string;
  disease_id?: number;
  limit?: number;
}): Promise<NewsSignal[]> {
  const qs = new URLSearchParams();
  if (params.county_fips) qs.set("county_fips", params.county_fips);
  if (params.disease_id !== undefined)
    qs.set("disease_id", String(params.disease_id));
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  const query = qs.toString() ? `?${qs}` : "";
  return get<NewsSignal[]>(`/news/signals${query}`);
}

export function fetchAlerts(params: {
  county_fips?: string;
  disease_id?: number;
  severity?: string;
  active_only?: boolean;
}): Promise<Alert[]> {
  const qs = new URLSearchParams();
  if (params.county_fips) qs.set("county_fips", params.county_fips);
  if (params.disease_id !== undefined)
    qs.set("disease_id", String(params.disease_id));
  if (params.severity) qs.set("severity", params.severity);
  if (params.active_only !== undefined)
    qs.set("active_only", String(params.active_only));
  const query = qs.toString() ? `?${qs}` : "";
  return get<Alert[]>(`/alerts/${query}`);
}

export function fetchCaseTrend(
  fips_code: string,
  params: { disease_id?: number; date_from?: string; date_to?: string }
): Promise<TrendPoint[]> {
  const qs = new URLSearchParams();
  if (params.disease_id !== undefined)
    qs.set("disease_id", String(params.disease_id));
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  const query = qs.toString() ? `?${qs}` : "";
  return get<TrendPoint[]>(`/cases/trend/${fips_code}${query}`);
}

export function fetchAgeBreakdown(
  fips_code: string,
  params: { disease_id?: number; date_from?: string; date_to?: string }
): Promise<AgeBreakdownRow[]> {
  const qs = new URLSearchParams();
  if (params.disease_id !== undefined)
    qs.set("disease_id", String(params.disease_id));
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  const query = qs.toString() ? `?${qs}` : "";
  return get<AgeBreakdownRow[]>(`/cases/age-breakdown/${fips_code}${query}`);
}

export function fetchAcquisitionBreakdown(
  fips_code: string,
  params: { disease_id?: number; date_from?: string; date_to?: string }
): Promise<AcquisitionBreakdownRow[]> {
  const qs = new URLSearchParams();
  if (params.disease_id !== undefined)
    qs.set("disease_id", String(params.disease_id));
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  const query = qs.toString() ? `?${qs}` : "";
  return get<AcquisitionBreakdownRow[]>(
    `/cases/acquisition-breakdown/${fips_code}${query}`
  );
}
