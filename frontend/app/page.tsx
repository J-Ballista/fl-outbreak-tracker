"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import FilterBar from "@/app/components/FilterBar";
import { useCasesSummary, useCounties, useDiseases } from "@/app/hooks/useMapData";

// FloridaMap uses D3 DOM APIs — load client-side only
const FloridaMap = dynamic(() => import("@/app/components/FloridaMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-96 w-full items-center justify-center rounded-xl bg-slate-100 text-slate-400">
      Loading map…
    </div>
  ),
});

export default function DashboardPage() {
  // Filter state
  const [selectedDiseaseId, setSelectedDiseaseId] = useState<number | undefined>();
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Data fetching
  const { data: counties = [] } = useCounties();
  const { data: diseases = [] } = useDiseases();
  const { data: summaryRows = [], isLoading: summaryLoading } = useCasesSummary({
    disease_id: selectedDiseaseId,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  // Build FIPS → case count map for the map component
  const casesByFips = useMemo<Map<string, number>>(
    () => new Map(summaryRows.map((r) => [r.county_fips, r.total_cases])),
    [summaryRows]
  );

  // Summary stats for the header bar
  const totalCases = useMemo(
    () => summaryRows.reduce((sum, r) => sum + r.total_cases, 0),
    [summaryRows]
  );
  const countiesWithCases = summaryRows.filter((r) => r.total_cases > 0).length;
  const selectedDisease = diseases.find((d) => d.id === selectedDiseaseId);

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      {/* ------------------------------------------------------------------ */}
      {/* Header                                                               */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-blue-900 px-6 py-4 shadow-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              Florida Outbreak Tracker
            </h1>
            <p className="text-sm text-blue-300">
              Vaccine-preventable disease surveillance · 67 counties
            </p>
          </div>
          <div className="flex gap-6 text-right">
            <div>
              <p className="text-2xl font-bold text-white">
                {totalCases.toLocaleString()}
              </p>
              <p className="text-xs text-blue-300">total cases</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{countiesWithCases}</p>
              <p className="text-xs text-blue-300">counties affected</p>
            </div>
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {/* Filter bar */}
        <FilterBar
          diseases={diseases}
          selectedDiseaseId={selectedDiseaseId}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDiseaseChange={setSelectedDiseaseId}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
        />

        {/* Active filter summary */}
        {(selectedDisease || dateFrom || dateTo) && (
          <p className="mt-3 text-sm text-slate-500">
            Showing{" "}
            <span className="font-medium text-slate-700">
              {selectedDisease?.name ?? "all diseases"}
            </span>
            {dateFrom && (
              <>
                {" "}from{" "}
                <span className="font-medium text-slate-700">{dateFrom}</span>
              </>
            )}
            {dateTo && (
              <>
                {" "}to{" "}
                <span className="font-medium text-slate-700">{dateTo}</span>
              </>
            )}
          </p>
        )}

        {/* Map + loading overlay */}
        <div className="relative mt-4">
          {summaryLoading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-white/60 backdrop-blur-sm">
              <span className="text-sm text-slate-500">Updating…</span>
            </div>
          )}
          <FloridaMap casesByFips={casesByFips} />
        </div>

        {/* County table */}
        <section className="mt-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            County breakdown
          </h2>
          <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">
                    County
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">
                    Total Cases
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">
                    Per 100k
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {summaryRows
                  .slice()
                  .sort((a, b) => b.total_cases - a.total_cases)
                  .slice(0, 20)
                  .map((row) => {
                    const county = counties.find(
                      (c) => c.fips_code === row.county_fips
                    );
                    const per100k =
                      county?.population && county.population > 0
                        ? ((row.total_cases / county.population) * 100_000).toFixed(1)
                        : "—";
                    return (
                      <tr key={row.county_fips} className="hover:bg-slate-50">
                        <td className="px-4 py-2 font-medium text-slate-800">
                          {county?.name ?? row.county_fips}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-700">
                          {row.total_cases.toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-500">
                          {per100k}
                        </td>
                      </tr>
                    );
                  })}
                {summaryRows.length === 0 && !summaryLoading && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-4 py-6 text-center text-slate-400"
                    >
                      No case data for the selected filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <footer className="py-4 text-center text-xs text-slate-400">
        Data: FL Health CHARTS · FL DOH VPD Reports · Local news signals
      </footer>
    </div>
  );
}
