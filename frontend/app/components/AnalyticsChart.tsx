"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { TrendPoint, VaccTrendPoint } from "@/app/lib/api";

interface AnalyticsChartProps {
  caseTrend: TrendPoint[];
  vaccTrend: VaccTrendPoint[];
  safeExemptThreshold: number | null;
  medicalContraindicationPct: number | null;
  countyName?: string;
  diseaseName?: string;
}

function fmt(v: number): string {
  return v % 1 === 0 ? String(v) : v.toFixed(1);
}

const VB_W = 800;
const VB_H = 400;
const MARGIN = { top: 24, right: 72, bottom: 48, left: 56 };

export default function AnalyticsChart({
  caseTrend,
  vaccTrend,
  safeExemptThreshold,
  medicalContraindicationPct,
  countyName,
  diseaseName,
}: AnalyticsChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const w = VB_W - MARGIN.left - MARGIN.right;
    const h = VB_H - MARGIN.top - MARGIN.bottom;

    const g = svg
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    // ── Empty / placeholder states ───────────────────────────────────────────

    if (caseTrend.length === 0) {
      g.append("text")
        .attr("x", w / 2).attr("y", h / 2)
        .attr("text-anchor", "middle")
        .attr("fill", "#94a3b8").attr("font-size", 14)
        .text(
          countyName
            ? "No data for selected filters"
            : "Select a county to view trend data"
        );
      return;
    }

    const hasVacc = vaccTrend.length > 0 || safeExemptThreshold != null || medicalContraindicationPct != null;

    // ── Parse data ───────────────────────────────────────────────────────────

    const parsedCases = caseTrend.map((d) => ({
      date: new Date(d.report_date),
      value: d.total_cases,
    }));

    // Invert vaccinated_pct → exempt_pct so rising line = rising risk
    const parsedVacc = vaccTrend.map((d) => ({
      date: new Date(d.survey_year, 6, 1), // Jul 1 of survey year
      value: +(100 - d.vaccinated_pct).toFixed(2),
    }));

    // ── Shared X scale ───────────────────────────────────────────────────────

    const allDates = [
      ...parsedCases.map((d) => d.date),
      ...parsedVacc.map((d) => d.date),
    ];
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, w]);

    // ── Y scales ─────────────────────────────────────────────────────────────

    const maxCases = d3.max(parsedCases, (d) => d.value) ?? 1;
    const yLeft = d3
      .scaleLinear()
      .domain([0, maxCases * 1.15])
      .range([h, 0])
      .nice();

    const vaccValues = [
      ...parsedVacc.map((d) => d.value),
      ...(safeExemptThreshold != null ? [safeExemptThreshold] : []),
      ...(medicalContraindicationPct != null ? [medicalContraindicationPct] : []),
    ];
    const vaccCenter = vaccValues.length
      ? vaccValues.reduce((a, b) => a + b, 0) / vaccValues.length
      : 85;
    const spread = Math.max(
      10,
      vaccValues.length >= 2
        ? (Math.max(...vaccValues) - Math.min(...vaccValues)) * 1.5
        : 12
    );
    const vaccMin = Math.max(0, vaccCenter - spread);
    const vaccMax = Math.min(100, vaccCenter + spread);
    const yRight = d3.scaleLinear().domain([vaccMin, vaccMax]).range([h, 0]);

    // ── Grid lines ───────────────────────────────────────────────────────────

    g.append("g")
      .call(d3.axisLeft(yLeft).ticks(5).tickSize(-w).tickFormat(() => ""))
      .call((ag) => ag.select(".domain").remove())
      .call((ag) =>
        ag.selectAll(".tick line")
          .attr("stroke", "#e2e8f0")
          .attr("stroke-dasharray", "3,3")
      );

    // ── Left axis (cases) ─────────────────────────────────────────────────────

    g.append("g")
      .call(
        d3.axisLeft(yLeft).ticks(5).tickFormat((v) => {
          const n = Number(v);
          return n >= 1000 ? `${fmt(n / 1000)}k` : fmt(n);
        })
      )
      .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
      .call((ag) => ag.selectAll(".tick text").attr("fill", "#475569").attr("font-size", 12))
      .call((ag) => ag.selectAll(".tick line").attr("stroke", "#cbd5e1"));

    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -h / 2).attr("y", -42)
      .attr("text-anchor", "middle")
      .attr("fill", "#ef4444").attr("font-size", 12).attr("font-weight", "600")
      .text("Cases");

    // ── Right axis (vacc %) ────────────────────────────────────────────────

    if (hasVacc) {
      g.append("g")
        .attr("transform", `translate(${w},0)`)
        .call(
          d3.axisRight(yRight).ticks(5).tickFormat((v) => `${fmt(Number(v))}%`)
        )
        .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
        .call((ag) => ag.selectAll(".tick text").attr("fill", "#475569").attr("font-size", 12))
        .call((ag) => ag.selectAll(".tick line").attr("stroke", "#cbd5e1"));

      g.append("text")
        .attr("transform", "rotate(90)")
        .attr("x", h / 2).attr("y", -(w + 56))
        .attr("text-anchor", "middle")
        .attr("fill", "#c2410c").attr("font-size", 12).attr("font-weight", "600")
        .text("Exempt %");
    }

    // ── X axis ────────────────────────────────────────────────────────────────

    const tickCount = Math.min(parsedCases.length, 8);
    g.append("g")
      .attr("transform", `translate(0,${h})`)
      .call(
        d3.axisBottom(xScale)
          .ticks(tickCount)
          .tickFormat(d3.timeFormat("%b %Y") as (v: Date | d3.NumberValue) => string)
      )
      .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
      .call((ag) => ag.selectAll(".tick text").attr("fill", "#475569").attr("font-size", 11))
      .call((ag) => ag.selectAll(".tick line").attr("stroke", "#cbd5e1"));

    // ── Case area + line ──────────────────────────────────────────────────────

    g.append("path")
      .datum(parsedCases)
      .attr("fill", "rgba(239,68,68,0.10)")
      .attr(
        "d",
        d3.area<{ date: Date; value: number }>()
          .x((d) => xScale(d.date))
          .y0(h).y1((d) => yLeft(d.value))
          .curve(d3.curveMonotoneX)
      );

    g.append("path")
      .datum(parsedCases)
      .attr("fill", "none")
      .attr("stroke", "#ef4444")
      .attr("stroke-width", 2.5)
      .attr(
        "d",
        d3.line<{ date: Date; value: number }>()
          .x((d) => xScale(d.date))
          .y((d) => yLeft(d.value))
          .curve(d3.curveMonotoneX)
      );

    // ── Exemption trend (orange-red — rising = rising risk) ──────────────────

    if (parsedVacc.length > 0) {
      if (parsedVacc.length > 1) {
        g.append("path")
          .datum(parsedVacc)
          .attr("fill", "none")
          .attr("stroke", "#c2410c")
          .attr("stroke-width", 2.5)
          .attr(
            "d",
            d3.line<{ date: Date; value: number }>()
              .x((d) => xScale(d.date))
              .y((d) => yRight(d.value))
              .curve(d3.curveMonotoneX)
          );
      }

      g.selectAll("circle.vacc-dot")
        .data(parsedVacc)
        .join("circle")
        .attr("class", "vacc-dot")
        .attr("cx", (d) => xScale(d.date))
        .attr("cy", (d) => yRight(d.value))
        .attr("r", 5)
        .attr("fill", "#c2410c")
        .attr("stroke", "#fff")
        .attr("stroke-width", 1.5);
    }

    // ── Amber dotted: safe religious-exemption ceiling ───────────────────────

    if (safeExemptThreshold != null) {
      const ty = yRight(safeExemptThreshold);
      g.append("line")
        .attr("x1", 0).attr("x2", w)
        .attr("y1", ty).attr("y2", ty)
        .attr("stroke", "#d97706")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "6,4");

      g.append("text")
        .attr("x", w + 4).attr("y", ty + 4)
        .attr("fill", "#d97706")
        .attr("font-size", 11).attr("font-weight", "700")
        .text(`Safe <${fmt(safeExemptThreshold)}%`);
    }

    // ── Blue dotted: medical contraindication baseline ────────────────────────

    if (medicalContraindicationPct != null) {
      const ty = yRight(medicalContraindicationPct);
      g.append("line")
        .attr("x1", 0).attr("x2", w)
        .attr("y1", ty).attr("y2", ty)
        .attr("stroke", "#3b82f6")
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "4,4");

      g.append("text")
        .attr("x", w + 4).attr("y", ty + 4)
        .attr("fill", "#3b82f6")
        .attr("font-size", 10).attr("font-weight", "600")
        .text(`Med. ${fmt(medicalContraindicationPct)}%`);
    }

    // ── Interactive hover ─────────────────────────────────────────────────────

    const bisectDate = d3.bisector((d: { date: Date }) => d.date).left;

    const hoverGroup = g.append("g").style("display", "none");

    hoverGroup.append("line")
      .attr("class", "h-line")
      .attr("y1", 0).attr("y2", h)
      .attr("stroke", "#94a3b8").attr("stroke-width", 1).attr("stroke-dasharray", "3,3");

    hoverGroup.append("circle")
      .attr("class", "h-dot-case")
      .attr("r", 5)
      .attr("fill", "#ef4444").attr("stroke", "#fff").attr("stroke-width", 2);

    hoverGroup.append("circle")
      .attr("class", "h-dot-vacc")
      .attr("r", 5)
      .attr("fill", "#c2410c").attr("stroke", "#fff").attr("stroke-width", 2)
      .style("display", "none");

    const tipG = hoverGroup.append("g");
    const tipRect = tipG.append("rect").attr("rx", 4).attr("fill", "#1e293b").attr("opacity", 0.9);
    const tipDate  = tipG.append("text").attr("fill", "#94a3b8").attr("font-size", 11).attr("font-weight", "500");
    const tipCases = tipG.append("text").attr("fill", "#fca5a5").attr("font-size", 13).attr("font-weight", "700");
    const tipVacc  = tipG.append("text").attr("fill", "#fdba74").attr("font-size", 12).attr("font-weight", "600");

    g.append("rect")
      .attr("width", w).attr("height", h)
      .attr("fill", "none")
      .style("pointer-events", "all")
      .on("mousemove", function (event: MouseEvent) {
        const [mx] = d3.pointer(event, this);
        const x0 = xScale.invert(mx);

        const ci = bisectDate(parsedCases, x0, 1);
        const c0 = parsedCases[ci - 1];
        const c1 = parsedCases[ci];
        const cp =
          !c1 || x0.valueOf() - c0.date.valueOf() < c1.date.valueOf() - x0.valueOf()
            ? c0 : c1;

        const cpx = xScale(cp.date);
        const cpy = yLeft(cp.value);

        hoverGroup.style("display", null);
        hoverGroup.select(".h-line").attr("x1", cpx).attr("x2", cpx);
        hoverGroup.select(".h-dot-case").attr("cx", cpx).attr("cy", cpy);

        let vaccLine = "";
        if (parsedVacc.length > 0) {
          const vi = bisectDate(parsedVacc, x0, 1);
          const v0 = parsedVacc[Math.max(0, vi - 1)];
          const v1 = parsedVacc[vi];
          const vp =
            !v1 || x0.valueOf() - v0.date.valueOf() < v1.date.valueOf() - x0.valueOf()
              ? v0 : v1;
          const vpy = yRight(vp.value);
          hoverGroup.select(".h-dot-vacc").style("display", null)
            .attr("cx", xScale(vp.date)).attr("cy", vpy);
          vaccLine = `Exempt ${fmt(vp.value)}% (${vp.date.getFullYear()})`;
        } else {
          hoverGroup.select(".h-dot-vacc").style("display", "none");
        }

        const dateStr = cp.date.toLocaleDateString("en-US", { month: "short", year: "numeric" });

        tipDate.attr("x", 8).attr("y", 16).text(dateStr);
        tipCases.attr("x", 8).attr("y", 34).text(`${cp.value.toLocaleString()} cases`);
        tipVacc.attr("x", 8).attr("y", 51).text(vaccLine).style("display", vaccLine ? "" : "none");

        const lineCount = vaccLine ? 3 : 2;
        const boxW = Math.max(
          (tipDate.node() as SVGTextElement).getBBox().width,
          (tipCases.node() as SVGTextElement).getBBox().width,
          vaccLine ? (tipVacc.node() as SVGTextElement).getBBox().width : 0,
        ) + 20;
        const boxH = lineCount === 3 ? 60 : 44;

        let tipX = cpx + 12;
        if (tipX + boxW > w) tipX = cpx - boxW - 12;
        const tipY = Math.max(0, Math.min(cpy - boxH / 2, h - boxH));

        tipG.attr("transform", `translate(${tipX},${tipY})`);
        tipRect.attr("x", 0).attr("y", 0).attr("width", boxW).attr("height", boxH);
      })
      .on("mouseleave", () => hoverGroup.style("display", "none"));

  }, [caseTrend, vaccTrend, safeExemptThreshold, medicalContraindicationPct, countyName]);

  return (
    <div>
      {(countyName || diseaseName) && (
        <p className="mb-2 text-sm font-medium text-slate-600">
          {[countyName ? `${countyName} County` : null, diseaseName]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        className="w-full overflow-visible"
        aria-label="Disease trend analytics chart"
      />
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-6 bg-red-500" style={{ height: 2 }} />
          Cases (left axis)
        </span>
        {vaccTrend.length > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-6 bg-orange-700" style={{ height: 2 }} />
            Exempt rate YoY (right axis)
          </span>
        )}
        {safeExemptThreshold != null && (
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block w-6"
              style={{
                height: 2,
                background:
                  "repeating-linear-gradient(90deg,#d97706 0,#d97706 5px,transparent 5px,transparent 9px)",
              }}
            />
            Safe exempt ceiling (&lt;{fmt(safeExemptThreshold)}%)
          </span>
        )}
        {medicalContraindicationPct != null && (
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block w-6"
              style={{
                height: 2,
                background:
                  "repeating-linear-gradient(90deg,#3b82f6 0,#3b82f6 4px,transparent 4px,transparent 8px)",
              }}
            />
            Medical contraindications ({fmt(medicalContraindicationPct)}%)
          </span>
        )}
      </div>
    </div>
  );
}
