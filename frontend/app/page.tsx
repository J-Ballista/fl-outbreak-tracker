"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import FilterBar from "@/app/components/FilterBar";
import CountyDetailPanel from "@/app/components/CountyDetailPanel";
import {
  useCasesSummary,
  useCounties,
  useDiseases,
  useVaccinationSummary,
  useCountyVaccRates,
  useNewsSignals,
  useAlerts,
  useCaseTrend,
  useAgeBreakdown,
  useAcquisitionBreakdown,
} from "@/app/hooks/useMapData";
import type { LayerMode, AlertSeverity } from "@/app/components/FloridaMap";

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
  // ── Filter state ──
  const [selectedDiseaseId, setSelectedDiseaseId] = useState<number | undefined>();
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // ── Layer toggle ──
  const [layerMode, setLayerMode] = useState<LayerMode>("cases");

  // ── Selected county for detail panel ──
  const [selectedCounty, setSelectedCounty] = useState<{
    fips: string;
    name: string;
  } | null>(null);

  // ── Data fetching ──
  const { data: counties = [] } = useCounties();
  const { data: diseases = [] } = useDiseases();
  const { data: summaryRows = [], isLoading: summaryLoading } = useCasesSummary({
    disease_id: selectedDiseaseId,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });
  const { data: vaccRows = [] } = useVaccinationSummary({
    disease_id: selectedDiseaseId,
  });
  const { data: countyVaccRates = [] } = useCountyVaccRates(selectedCounty?.fips);
  const { data: newsSignals = [] } = useNewsSignals({
    county_fips: selectedCounty?.fips,
    disease_id: selectedDiseaseId,
  });
  const { data: allAlerts = [] } = useAlerts({ active_only: true });
  const { data: countyAlerts = [] } = useAlerts({
    county_fips: selectedCounty?.fips,
    active_only: true,
  });
  const { data: caseTrend = [] } = useCaseTrend(selectedCounty?.fips, {
    disease_id: selectedDiseaseId,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });
  const { data: ageBreakdown = [] } = useAgeBreakdown(selectedCounty?.fips, {
    disease_id: selectedDiseaseId,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });
  const { data: acquisitionBreakdown = [] } = useAcquisitionBreakdown(
    selectedCounty?.fips,
    {
      disease_id: selectedDiseaseId,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }
  );

  // ── Derived maps ──
  const casesByFips = useMemo<Map<string, number>>(
    () => new Map(summaryRows.map((r) => [r.county_fips, r.total_cases])),
    [summaryRows]
  );

  const vaccinationByFips = useMemo<Map<string, number>>(
    () => new Map(vaccRows.map((r) => [r.county_fips, r.vaccinated_pct])),
    [vaccRows]
  );

  // Highest-severity alert per county for map overlay
  const alertsByFips = useMemo<Map<string, AlertSeverity>>(() => {
    const severityOrder: Record<AlertSeverity, number> = {
      watch: 1,
      warning: 2,
      emergency: 3,
    };
    const map = new Map<string, AlertSeverity>();
    for (const alert of allAlerts) {
      const existing = map.get(alert.county_fips);
      if (
        !existing ||
        severityOrder[alert.severity] > severityOrder[existing]
      ) {
        map.set(alert.county_fips, alert.severity);
      }
    }
    return map;
  }, [allAlerts]);

  // ── Summary stats ──
  const totalCases = useMemo(
    () => summaryRows.reduce((sum, r) => sum + r.total_cases, 0),
    [summaryRows]
  );
  const countiesWithCases = summaryRows.filter((r) => r.total_cases > 0).length;
  const selectedDisease = diseases.find((d) => d.id === selectedDiseaseId);

  // ── County detail data ──
  const selectedCountyCases = useMemo(
    () => summaryRows.find((r) => r.county_fips === selectedCounty?.fips) ?? null,
    [summaryRows, selectedCounty]
  );
  const selectedCountyVacc = useMemo(
    () => vaccRows.find((r) => r.county_fips === selectedCounty?.fips) ?? null,
    [vaccRows, selectedCounty]
  );

  function handleCountyClick(fips: string, name: string) {
    setSelectedCounty((prev) => (prev?.fips === fips ? null : { fips, name }));
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      {/* ── Header ── */}
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
          <div className="flex items-center gap-6 text-right">
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
            {/* Alert badge */}
            {allAlerts.length > 0 && (
              <div className="flex items-center gap-1.5 rounded-full bg-red-600 px-3 py-1.5 shadow-sm">
                <span className="text-sm font-bold text-white">
                  ⚠ {allAlerts.length}
                </span>
                <span className="text-xs text-red-200">active alerts</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {/* Filter bar */}
        <FilterBar
          diseases={diseases}
          selectedDiseaseId={selectedDiseaseId}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDiseaseChange={setSelectedDiseaseId}
          onDateChange={(from, to) => {
            setDateFrom(from);
            setDateTo(to);
          }}
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
                {" "}
                from{" "}
                <span className="font-medium text-slate-700">{dateFrom}</span>
              </>
            )}
            {dateTo && (
              <>
                {" "}
                to{" "}
                <span className="font-medium text-slate-700">{dateTo}</span>
              </>
            )}
          </p>
        )}

        {/* Layer toggle + map */}
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-2">
            {(["cases", "vaccination"] as LayerMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setLayerMode(mode)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  layerMode === mode
                    ? "bg-blue-700 text-white shadow-sm"
                    : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {mode === "cases" ? "Cases" : "Vaccination Rate"}
              </button>
            ))}
            {selectedCounty && (
              <span className="ml-auto text-sm text-slate-500">
                Click a county to deselect, or close the panel
              </span>
            )}
          </div>

          {/* Map + loading overlay */}
          <div className="relative">
            {summaryLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-white/60 backdrop-blur-sm">
                <span className="text-sm text-slate-500">Updating…</span>
              </div>
            )}
            <FloridaMap
              casesByFips={casesByFips}
              vaccinationByFips={vaccinationByFips}
              alertsByFips={alertsByFips}
              layerMode={layerMode}
              onCountyClick={handleCountyClick}
            />
          </div>
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
                    Confirmed
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">
                    Probable
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">
                    Per 100k
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">
                    Vacc %
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">
                    Alert
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
                        ? (
                            (row.total_cases / county.population) *
                            100_000
                          ).toFixed(1)
                        : "—";
                    const vacc = vaccRows.find(
                      (v) => v.county_fips === row.county_fips
                    );
                    const alertSeverity = alertsByFips.get(row.county_fips);
                    const alertColors: Record<string, string> = {
                      emergency: "bg-red-100 text-red-700",
                      warning: "bg-orange-100 text-orange-700",
                      watch: "bg-amber-100 text-amber-700",
                    };
                    return (
                      <tr
                        key={row.county_fips}
                        className={`cursor-pointer hover:bg-slate-50 ${
                          selectedCounty?.fips === row.county_fips
                            ? "bg-blue-50"
                            : ""
                        }`}
                        onClick={() =>
                          handleCountyClick(
                            row.county_fips,
                            county?.name ?? row.county_fips
                          )
                        }
                      >
                        <td className="px-4 py-2 font-medium text-slate-800">
                          {county?.name ?? row.county_fips}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-700">
                          {row.total_cases.toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-500">
                          {row.confirmed_total > 0
                            ? row.confirmed_total.toLocaleString()
                            : "—"}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-500">
                          {row.probable_total > 0
                            ? row.probable_total.toLocaleString()
                            : "—"}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-500">
                          {per100k}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-500">
                          {vacc ? `${vacc.vaccinated_pct.toFixed(1)}%` : "—"}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {alertSeverity ? (
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${alertColors[alertSeverity]}`}
                            >
                              {alertSeverity}
                            </span>
                          ) : (
                            <span className="text-slate-300">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                {summaryRows.length === 0 && !summaryLoading && (
                  <tr>
                    <td
                      colSpan={7}
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

      {/* County detail panel (slide-out) */}
      <CountyDetailPanel
        county={
          selectedCounty
            ? (counties.find((c) => c.fips_code === selectedCounty.fips) ?? null)
            : null
        }
        cases={selectedCountyCases}
        vaccSummary={selectedCountyVacc}
        vaccByDisease={countyVaccRates}
        signals={newsSignals}
        diseases={diseases}
        alerts={countyAlerts}
        trend={caseTrend}
        ageBreakdown={ageBreakdown}
        acquisitionBreakdown={acquisitionBreakdown}
        onClose={() => setSelectedCounty(null)}
      />
    </div>
  );
}
