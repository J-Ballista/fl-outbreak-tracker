"use client";

import useSWR from "swr";
import {
  fetchCounties,
  fetchDiseases,
  fetchCasesSummary,
  fetchVaccinationSummary,
  fetchCountyVaccRates,
  fetchCountyVaccTrend,
  fetchNewsSignals,
  fetchAlerts,
  fetchCaseTrend,
  fetchAgeBreakdown,
  fetchAcquisitionBreakdown,
} from "@/app/lib/api";

export function useCounties() {
  return useSWR("counties", fetchCounties, { revalidateOnFocus: false });
}

export function useDiseases() {
  return useSWR("diseases", fetchDiseases, { revalidateOnFocus: false });
}

export function useCasesSummary(params: {
  disease_id?: number;
  date_from?: string;
  date_to?: string;
}) {
  const key = params.disease_id || params.date_from || params.date_to
    ? ["cases-summary", params.disease_id, params.date_from, params.date_to]
    : "cases-summary";

  return useSWR(key, () => fetchCasesSummary(params), {
    revalidateOnFocus: false,
  });
}

export function useVaccinationSummary(params: {
  disease_id?: number;
  survey_year?: number;
}) {
  const key = ["vacc-summary", params.disease_id, params.survey_year];
  return useSWR(key, () => fetchVaccinationSummary(params), {
    revalidateOnFocus: false,
  });
}

export function useCountyVaccRates(fips_code: string | null | undefined) {
  return useSWR(
    fips_code ? ["county-vacc-rates", fips_code] : null,
    () => fetchCountyVaccRates(fips_code!),
    { revalidateOnFocus: false }
  );
}

export function useCountyVaccTrend(
  fips_code: string | null | undefined,
  disease_id?: number
) {
  return useSWR(
    fips_code ? ["county-vacc-trend", fips_code, disease_id] : null,
    () => fetchCountyVaccTrend(fips_code!, disease_id),
    { revalidateOnFocus: false }
  );
}

export function useNewsSignals(params: {
  county_fips?: string;
  disease_id?: number;
  limit?: number;
}) {
  // Only fetch when a county is selected (county_fips defined)
  const key = params.county_fips
    ? ["news-signals", params.county_fips, params.disease_id, params.limit]
    : null;
  return useSWR(key, () => fetchNewsSignals(params), {
    revalidateOnFocus: false,
  });
}

export function useAlerts(params: {
  county_fips?: string;
  disease_id?: number;
  severity?: string;
  active_only?: boolean;
}) {
  const key = ["alerts", params.county_fips, params.disease_id, params.severity, params.active_only];
  return useSWR(key, () => fetchAlerts(params), { revalidateOnFocus: false });
}

export function useCaseTrend(
  fips_code: string | null | undefined,
  params: { disease_id?: number; date_from?: string; date_to?: string }
) {
  const key = fips_code
    ? ["case-trend", fips_code, params.disease_id, params.date_from, params.date_to]
    : null;
  return useSWR(key, () => fetchCaseTrend(fips_code!, params), {
    revalidateOnFocus: false,
  });
}

export function useAgeBreakdown(
  fips_code: string | null | undefined,
  params: { disease_id?: number; date_from?: string; date_to?: string }
) {
  const key = fips_code
    ? ["age-breakdown", fips_code, params.disease_id, params.date_from, params.date_to]
    : null;
  return useSWR(key, () => fetchAgeBreakdown(fips_code!, params), {
    revalidateOnFocus: false,
  });
}

export function useAcquisitionBreakdown(
  fips_code: string | null | undefined,
  params: { disease_id?: number; date_from?: string; date_to?: string }
) {
  const key = fips_code
    ? ["acq-breakdown", fips_code, params.disease_id, params.date_from, params.date_to]
    : null;
  return useSWR(key, () => fetchAcquisitionBreakdown(fips_code!, params), {
    revalidateOnFocus: false,
  });
}
