"use client";

import useSWR from "swr";
import {
  fetchCounties,
  fetchDiseases,
  fetchCasesSummary,
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
