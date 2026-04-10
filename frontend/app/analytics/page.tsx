"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import MonthRangeSlider from "@/app/components/MonthRangeSlider";
import {
  useCounties,
  useDiseases,
  useCaseTrend,
  useCountyVaccTrend,
} from "@/app/hooks/useMapData";
import {
  safeExemptThreshold as computeSafeExempt,
  safeExemptThresholdComposite,
  avgMedicalContraindication,
} from "@/app/lib/api";

const AnalyticsChart = dynamic(() => import("@/app/components/AnalyticsChart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-64 w-full items-center justify-center text-slate-400">
      Loading chart…
    </div>
  ),
});

export default function AnalyticsPage() {
  const [selectedDiseaseId, setSelectedDiseaseId] = useState<number | undefined>();
  const [selectedFips, setSelectedFips] = useState<string | undefined>();
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data: diseases = [] } = useDiseases();
  const { data: counties = [] } = useCounties();

  const { data: caseTrend = [] } = useCaseTrend(selectedFips, {
    disease_id: selectedDiseaseId,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const { data: vaccTrend = [] } = useCountyVaccTrend(selectedFips, selectedDiseaseId);

  const selectedDisease = useMemo(
    () => diseases.find((d) => d.id === selectedDiseaseId),
    [diseases, selectedDiseaseId]
  );

  const chartSafeExempt = selectedDisease
    ? computeSafeExempt(selectedDisease)
    : safeExemptThresholdComposite(diseases);

  const chartMedicalPct = selectedDisease
    ? (selectedDisease.medical_contraindication_pct ?? 0.3)
    : avgMedicalContraindication(diseases);

  const selectedCounty = useMemo(
    () => counties.find((c) => c.fips_code === selectedFips),
    [counties, selectedFips]
  );

  const sortedCounties = useMemo(
    () => [...counties].sort((a, b) => a.name.localeCompare(b.name)),
    [counties]
  );

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      {/* Header */}
      <header className="bg-blue-900 px-6 py-4 shadow-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              Florida Outbreak Tracker
            </h1>
            <p className="text-sm text-blue-300">Analytics — Time-series explorer</p>
          </div>
          <Link
            href="/"
            className="rounded-full bg-blue-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-600"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {/* Filter row */}
        <div className="flex flex-wrap items-center gap-4 rounded-xl bg-white px-5 py-4 shadow-sm ring-1 ring-slate-200">
          {/* Disease select */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">Disease</label>
            <select
              value={selectedDiseaseId ?? ""}
              onChange={(e) =>
                setSelectedDiseaseId(e.target.value ? Number(e.target.value) : undefined)
              }
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All diseases</option>
              {diseases.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>

          {/* County select */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">County</label>
            <select
              value={selectedFips ?? ""}
              onChange={(e) => setSelectedFips(e.target.value || undefined)}
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select county…</option>
              {sortedCounties.map((c) => (
                <option key={c.fips_code} value={c.fips_code}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date range */}
          <div className="flex flex-col gap-1 flex-1 min-w-[260px]">
            <label className="text-xs font-medium text-slate-500">Period</label>
            <MonthRangeSlider
              dateFrom={dateFrom}
              dateTo={dateTo}
              onChange={(from, to) => {
                setDateFrom(from);
                setDateTo(to);
              }}
            />
          </div>
        </div>

        {/* Chart card */}
        <div className="mt-6 rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          {selectedDisease && (
            <div className="mb-4 flex flex-wrap gap-3">
              {selectedDisease.herd_threshold_pct != null && (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                  Herd threshold: {selectedDisease.herd_threshold_pct}%
                </span>
              )}
              {chartSafeExempt != null && (
                <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-200">
                  Safe exempt ceiling: &lt;{chartSafeExempt}%
                </span>
              )}
              <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-200">
                Medical contraindications: {chartMedicalPct}%
              </span>
              {selectedDisease.r0_estimate && (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                  R₀: {selectedDisease.r0_estimate}
                </span>
              )}
            </div>
          )}
          <AnalyticsChart
            caseTrend={caseTrend}
            vaccTrend={vaccTrend}
            safeExemptThreshold={chartSafeExempt}
            medicalContraindicationPct={chartMedicalPct}
            countyName={selectedCounty?.name}
            diseaseName={selectedDisease?.name}
          />
        </div>
      </main>

      <footer className="py-4 text-center text-xs text-slate-400">
        Data: FL Health CHARTS · FL DOH VPD Reports · Local news signals
      </footer>
    </div>
  );
}
