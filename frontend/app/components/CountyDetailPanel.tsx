"use client";

import type {
  County,
  CaseSummary,
  VaccinationSummary,
  CountyDiseaseVaccRate,
  VaccTrendPoint,
  NewsSignal,
  Disease,
  Alert,
  TrendPoint,
  AgeBreakdownRow,
  AcquisitionBreakdownRow,
} from "@/app/lib/api";
import {
  safeExemptThreshold as computeSafeExempt,
  safeExemptThresholdComposite,
  avgMedicalContraindication,
} from "@/app/lib/api";
import TrendSparkline from "./TrendSparkline";

interface CountyDetailPanelProps {
  county: County | null;
  cases: CaseSummary | null;
  vaccSummary: VaccinationSummary | null;
  vaccByDisease: CountyDiseaseVaccRate[];
  vaccTrend: VaccTrendPoint[];
  signals: NewsSignal[];
  diseases: Disease[];
  alerts: Alert[];
  trend: TrendPoint[];
  ageBreakdown: AgeBreakdownRow[];
  acquisitionBreakdown: AcquisitionBreakdownRow[];
  selectedDiseaseId?: number;
  onClose: () => void;
}

const SEVERITY_STYLES = {
  emergency: "bg-red-100 text-red-700 ring-1 ring-red-300",
  warning: "bg-orange-100 text-orange-700 ring-1 ring-orange-300",
  watch: "bg-amber-100 text-amber-700 ring-1 ring-amber-300",
};

function SeverityBadge({ severity }: { severity: string }) {
  const style =
    SEVERITY_STYLES[severity as keyof typeof SEVERITY_STYLES] ??
    "bg-slate-100 text-slate-600";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold uppercase ${style}`}>
      {severity}
    </span>
  );
}

function YoYBadge({ delta, invert = false }: { delta: number | null; invert?: boolean }) {
  if (delta === null) return <span className="text-xs text-slate-400">–</span>;
  const positive = delta >= 0;
  const isGood = invert ? !positive : positive;
  const sign = positive ? "↑" : "↓";
  return (
    <span
      className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${
        isGood ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
      }`}
    >
      {sign}{Math.abs(delta).toFixed(1)}%
    </span>
  );
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return null;
  const pct = Math.round((value ?? 0) * 100);
  const color =
    pct >= 85
      ? "bg-green-100 text-green-700"
      : pct >= 65
      ? "bg-yellow-100 text-yellow-700"
      : "bg-slate-100 text-slate-500";
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>
      {pct}% conf
    </span>
  );
}

export default function CountyDetailPanel({
  county,
  cases,
  vaccSummary,
  vaccByDisease,
  vaccTrend,
  signals,
  diseases,
  alerts,
  trend,
  ageBreakdown,
  acquisitionBreakdown,
  selectedDiseaseId,
  onClose,
}: CountyDetailPanelProps) {
  const open = county !== null;

  function diseaseName(id: number | null) {
    if (id === null) return "Unknown";
    return diseases.find((d) => d.id === id)?.name ?? `Disease ${id}`;
  }

  const totalAcquisition = acquisitionBreakdown.reduce(
    (sum, r) => sum + r.total_cases,
    0
  );

  // Safe exemption threshold for the sparkline amber dotted line
  const trendSafeExempt: number | null = (() => {
    if (selectedDiseaseId !== undefined) {
      const d = diseases.find((d) => d.id === selectedDiseaseId);
      return d ? computeSafeExempt(d) : null;
    }
    return safeExemptThresholdComposite(diseases);
  })();

  // Medical contraindication % for the sparkline blue dotted line
  const trendMedicalPct: number = (() => {
    if (selectedDiseaseId !== undefined) {
      const d = diseases.find((d) => d.id === selectedDiseaseId);
      return d?.medical_contraindication_pct ?? 0.3;
    }
    return avgMedicalContraindication(diseases);
  })();

  // YoY exemption rate delta — computed on exempt_pct = 100 - vaccinated_pct
  // Rising exemptions = bad, so badge uses invert=true at the call site
  const vaccYoY: number | null = (() => {
    if (vaccTrend.length < 2) return null;
    const sorted = [...vaccTrend].sort((a, b) => a.survey_year - b.survey_year);
    const latestExempt = 100 - sorted[sorted.length - 1].vaccinated_pct;
    const priorExempt = 100 - sorted[sorted.length - 2].vaccinated_pct;
    if (priorExempt === 0) return null;
    return ((latestExempt - priorExempt) / priorExempt) * 100;
  })();

  // YoY case count delta (group monthly trend by calendar year)
  const caseYoY: number | null = (() => {
    if (trend.length === 0) return null;
    const byYear = new Map<number, number>();
    for (const pt of trend) {
      const year = new Date(pt.report_date).getFullYear();
      byYear.set(year, (byYear.get(year) ?? 0) + pt.total_cases);
    }
    const years = [...byYear.keys()].sort((a, b) => a - b);
    if (years.length < 2) return null;
    const latest = byYear.get(years[years.length - 1])!;
    const prior = byYear.get(years[years.length - 2])!;
    if (prior === 0) return null;
    return ((latest - prior) / prior) * 100;
  })();

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[360px] bg-white shadow-2xl z-50 flex flex-col
          transform transition-transform duration-300 ease-in-out
          ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between bg-blue-900 px-5 py-4 shrink-0">
          <h2 className="text-base font-semibold text-white truncate">
            {county?.name ?? ""} County
          </h2>
          <button
            onClick={onClose}
            aria-label="Close panel"
            className="ml-3 shrink-0 text-blue-200 hover:text-white text-xl leading-none"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {/* ── Active Alerts ── */}
          {alerts.length > 0 && (
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Active Alerts
                <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-red-700 text-xs font-semibold">
                  {alerts.length}
                </span>
              </h3>
              <ul className="space-y-2">
                {alerts.map((alert) => (
                  <li
                    key={alert.id}
                    className="rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200 flex flex-col gap-1"
                  >
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={alert.severity} />
                      <span className="text-xs font-medium text-slate-700">
                        {diseaseName(alert.disease_id)}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">
                      {alert.metric === "case_spike"
                        ? `Case spike: ${alert.observed_value} cases (threshold ${alert.threshold_value?.toFixed(1)})`
                        : `Vacc rate ${alert.observed_value?.toFixed(1)}% < ${alert.threshold_value?.toFixed(0)}% herd threshold`}
                    </p>
                    <p className="text-xs text-slate-400">
                      {new Date(alert.alert_date).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* ── Cases KPIs ── */}
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Cases (selected period)
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {/* Total — with YoY badge */}
              <div className="rounded-lg bg-slate-50 p-3 text-center ring-1 ring-slate-200">
                <p className="text-xl font-bold text-slate-800">
                  {(cases?.total_cases ?? 0).toLocaleString()}
                </p>
                <p className="mt-0.5 text-xs text-slate-500 flex items-center justify-center flex-wrap gap-0.5">
                  Total
                  <YoYBadge delta={caseYoY} invert />
                </p>
              </div>
              {[
                { label: "Confirmed", value: cases?.confirmed_total ?? 0 },
                { label: "Probable", value: cases?.probable_total ?? 0 },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-lg bg-slate-50 p-3 text-center ring-1 ring-slate-200"
                >
                  <p className="text-xl font-bold text-slate-800">
                    {value.toLocaleString()}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">{label}</p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Trend Sparkline ── */}
          {trend.length > 0 && (
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Case Trend
              </h3>
              <div className="rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200">
                <TrendSparkline
                  caseTrend={trend}
                  vaccTrend={vaccTrend}
                  safeExemptThreshold={trendSafeExempt}
                  medicalContraindicationPct={trendMedicalPct}
                  width={292}
                  height={190}
                />
              </div>
            </section>
          )}

          {/* ── Age Breakdown ── */}
          {ageBreakdown.length > 0 && (
            <section>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Age Breakdown
              </h3>
              <div className="space-y-2">
                {ageBreakdown.map((row) => {
                  const maxCases = Math.max(...ageBreakdown.map((r) => r.total_cases));
                  const pct = maxCases > 0 ? (row.total_cases / maxCases) * 100 : 0;
                  return (
                    <div key={row.age_group} className="flex items-center gap-2">
                      <span className="w-16 shrink-0 text-right text-xs text-slate-500">
                        {row.age_group}
                      </span>
                      <div className="flex-1 h-4 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-blue-400 transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="w-10 shrink-0 text-xs font-medium text-slate-700">
                        {row.total_cases.toLocaleString()}
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* ── Acquisition Type ── */}
          {acquisitionBreakdown.length > 0 && (
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Acquisition
              </h3>
              <div className="flex flex-wrap gap-2">
                {acquisitionBreakdown.map((row) => {
                  const pct =
                    totalAcquisition > 0
                      ? Math.round((row.total_cases / totalAcquisition) * 100)
                      : 0;
                  return (
                    <span
                      key={row.acquisition}
                      className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
                    >
                      {row.acquisition}{" "}
                      <span className="font-bold text-slate-800">
                        {pct}%
                      </span>
                      <span className="ml-1 text-slate-500">
                        ({row.total_cases.toLocaleString()})
                      </span>
                    </span>
                  );
                })}
              </div>
            </section>
          )}

          {/* ── School Exemption Rate ── */}
          {vaccSummary !== null && (
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                School Exemption Rate
                <span className="ml-2 font-normal text-slate-400 normal-case">
                  {vaccSummary.survey_year} · religious
                </span>
              </h3>

              {(() => {
                const exemptPct =
                  vaccSummary.exempt_religious_pct != null
                    ? vaccSummary.exempt_religious_pct
                    : +(100 - vaccSummary.vaccinated_pct).toFixed(2);
                const isHighRisk = exemptPct > 10;
                const isMedRisk = exemptPct > 5;
                return (
                  <div className="rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200 mb-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-slate-700 flex items-center flex-wrap gap-1">
                        {exemptPct.toFixed(1)}% exempt avg
                        <YoYBadge delta={vaccYoY} invert />
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          isHighRisk ? "bg-red-500" : isMedRisk ? "bg-amber-500" : "bg-green-500"
                        }`}
                        style={{ width: `${Math.min(exemptPct * 4, 100)}%` }}
                      />
                    </div>
                    {isHighRisk ? (
                      <p className="mt-1.5 text-xs text-red-600 font-medium">
                        High exemption — immunity gap risk
                      </p>
                    ) : isMedRisk ? (
                      <p className="mt-1.5 text-xs text-amber-600 font-medium">
                        Moderate exemption — monitor closely
                      </p>
                    ) : null}
                  </div>
                );
              })()}

              {vaccByDisease.length > 0 && (
                <div className="overflow-hidden rounded-lg ring-1 ring-slate-200">
                  <table className="min-w-full text-xs">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-slate-500 font-medium">
                          Disease
                        </th>
                        <th className="px-3 py-2 text-right text-slate-500 font-medium">
                          Exempt %
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {vaccByDisease
                        .slice()
                        .sort((a, b) => b.vaccinated_pct - a.vaccinated_pct)
                        .map((r) => {
                          const ep = +(100 - r.vaccinated_pct).toFixed(2);
                          return (
                            <tr key={r.disease_id} className="hover:bg-slate-50">
                              <td className="px-3 py-1.5 text-slate-700">
                                {diseaseName(r.disease_id)}
                              </td>
                              <td
                                className={`px-3 py-1.5 text-right font-medium ${
                                  ep > 10
                                    ? "text-red-600"
                                    : ep > 5
                                    ? "text-amber-600"
                                    : "text-green-700"
                                }`}
                              >
                                {ep.toFixed(1)}%
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* ── News Signals ── */}
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              News Signals
              {signals.length > 0 && (
                <span className="ml-2 rounded-full bg-blue-100 px-2 py-0.5 text-blue-700">
                  {signals.length}
                </span>
              )}
            </h3>

            {signals.length === 0 ? (
              <p className="text-sm text-slate-400 italic">
                No news signals for this county.
              </p>
            ) : (
              <ul className="space-y-3">
                {signals.map((sig) => {
                  const pubDate = sig.article_published_at
                    ? new Date(sig.article_published_at).toLocaleDateString(
                        "en-US",
                        { month: "short", day: "numeric", year: "numeric" }
                      )
                    : null;

                  return (
                    <li
                      key={sig.id}
                      className="rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200"
                    >
                      <a
                        href={sig.article_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-blue-700 hover:text-blue-900 hover:underline leading-snug"
                      >
                        {sig.article_title ?? sig.article_url}
                      </a>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                        {sig.article_source && (
                          <span className="text-xs text-slate-500">
                            {sig.article_source}
                          </span>
                        )}
                        {pubDate && (
                          <span className="text-xs text-slate-400">
                            · {pubDate}
                          </span>
                        )}
                        <span className="text-xs text-slate-400">
                          · {diseaseName(sig.disease_id)}
                        </span>
                        {sig.extracted_case_count !== null && (
                          <span className="text-xs font-medium text-slate-600">
                            ~{sig.extracted_case_count} cases
                          </span>
                        )}
                        <ConfidenceBadge value={sig.confidence} />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
