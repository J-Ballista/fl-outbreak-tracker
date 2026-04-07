"use client";

import useSWR from "swr";
import {
  fetchCounties,
  fetchDiseases,
  fetchCasesSummary,
  fetchVaccinationSummary,
  fetchCountyVaccRates,
  fetchNewsSignals,
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
