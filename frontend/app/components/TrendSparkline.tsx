"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { TrendPoint } from "@/app/lib/api";

interface Props {
  data: TrendPoint[];
  vaccPct?: number | null;        // current vaccination rate 0–100 (green line)
  herdThreshold?: number | null;  // recommended threshold 0–100 (amber dotted)
  width?: number;
  height?: number;
}

/** Format a number to at most 1 decimal place, trimming trailing zeros. */
function fmt(v: number): string {
  return v % 1 === 0 ? String(v) : v.toFixed(1);
}

export default function TrendSparkline({
  data,
  vaccPct,
  herdThreshold,
  width = 292,
  height = 180,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const hasVacc = vaccPct != null || herdThreshold != null;
    const margin = { top: 16, right: hasVacc ? 52 : 14, bottom: 32, left: 44 };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    if (data.length === 0) {
      g.append("text")
        .attr("x", w / 2).attr("y", h / 2)
        .attr("text-anchor", "middle")
        .attr("fill", "#94a3b8").attr("font-size", 11)
        .text("No data for selected filters");
      return;
    }

    const parsed = data.map((d) => ({
      date: new Date(d.report_date),
      value: d.total_cases,
    }));

    // ── Scales ───────────────────────────────────────────────────────────────

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(parsed, (d) => d.date) as [Date, Date])
      .range([0, w]);

    const maxCases = d3.max(parsed, (d) => d.value) ?? 1;
    const yLeft = d3
      .scaleLinear()
      .domain([0, maxCases * 1.15])
      .range([h, 0])
      .nice();

    // Tighten right-axis domain around the actual vacc values so lines
    // aren't squeezed into the top 5% of the chart
    const vaccValues = [vaccPct, herdThreshold].filter((v): v is number => v != null);
    const vaccMin = vaccValues.length ? Math.max(0, Math.min(...vaccValues) - 8) : 0;
    const vaccMax = vaccValues.length ? Math.min(100, Math.max(...vaccValues) + 8) : 100;

    const yRight = d3.scaleLinear().domain([vaccMin, vaccMax]).range([h, 0]);

    // ── Grid lines ───────────────────────────────────────────────────────────

    g.append("g")
      .call(
        d3.axisLeft(yLeft).ticks(4).tickSize(-w).tickFormat(() => "")
      )
      .call((ag) => ag.select(".domain").remove())
      .call((ag) =>
        ag.selectAll(".tick line")
          .attr("stroke", "#e2e8f0")
          .attr("stroke-dasharray", "3,3")
      );

    // ── Left axis — case counts ───────────────────────────────────────────────

    g.append("g")
      .call(
        d3.axisLeft(yLeft).ticks(4).tickFormat((v) => {
          const n = Number(v);
          if (n >= 1000) return `${fmt(n / 1000)}k`;
          return fmt(n);
        })
      )
      .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
      .call((ag) => ag.selectAll(".tick text").attr("fill", "#475569").attr("font-size", 11))
      .call((ag) => ag.selectAll(".tick line").attr("stroke", "#cbd5e1"));

    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -h / 2).attr("y", -36)
      .attr("text-anchor", "middle")
      .attr("fill", "#ef4444").attr("font-size", 10).attr("font-weight", "600")
      .text("Cases");

    // ── Right axis — vaccination % ────────────────────────────────────────────

    if (hasVacc) {
      g.append("g")
        .attr("transform", `translate(${w},0)`)
        .call(
          d3.axisRight(yRight).ticks(4).tickFormat((v) => `${fmt(Number(v))}%`)
        )
        .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
        .call((ag) => ag.selectAll(".tick text").attr("fill", "#475569").attr("font-size", 11))
        .call((ag) => ag.selectAll(".tick line").attr("stroke", "#cbd5e1"));

      g.append("text")
        .attr("transform", "rotate(90)")
        .attr("x", h / 2).attr("y", -(w + 40))
        .attr("text-anchor", "middle")
        .attr("fill", "#15803d").attr("font-size", 10).attr("font-weight", "600")
        .text("Vacc %");
    }

    // ── Bottom X axis ─────────────────────────────────────────────────────────

    g.append("g")
      .attr("transform", `translate(0,${h})`)
      .call(
        d3.axisBottom(xScale)
          .ticks(Math.min(parsed.length, 5))
          .tickFormat(d3.timeFormat("%b %y") as (v: Date | d3.NumberValue) => string)
      )
      .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
      .call((ag) => ag.selectAll(".tick text").attr("fill", "#475569").attr("font-size", 11))
      .call((ag) => ag.selectAll(".tick line").attr("stroke", "#cbd5e1"));

    // ── Case area + line (red) ────────────────────────────────────────────────

    const area = d3.area<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y0(h).y1((d) => yLeft(d.value))
      .curve(d3.curveMonotoneX);

    const line = d3.line<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y((d) => yLeft(d.value))
      .curve(d3.curveMonotoneX);

    g.append("path").datum(parsed)
      .attr("fill", "rgba(239,68,68,0.12)")
      .attr("d", area);

    g.append("path").datum(parsed)
      .attr("fill", "none")
      .attr("stroke", "#ef4444")
      .attr("stroke-width", 2.5)
      .attr("d", line);

    // ── Herd-threshold dotted line (amber) ────────────────────────────────────

    if (herdThreshold != null && hasVacc) {
      const ty = yRight(herdThreshold);

      g.append("line")
        .attr("x1", 0).attr("x2", w)
        .attr("y1", ty).attr("y2", ty)
        .attr("stroke", "#d97706")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "6,4");

      // Label on the left side so it doesn't crowd the right axis
      g.append("text")
        .attr("x", 4).attr("y", ty - 5)
        .attr("fill", "#d97706")
        .attr("font-size", 10).attr("font-weight", "600")
        .text(`Herd ${fmt(herdThreshold)}%`);
    }

    // ── Vaccination rate line (dark green) ────────────────────────────────────

    if (vaccPct != null && hasVacc) {
      const vy = yRight(vaccPct);

      g.append("line")
        .attr("x1", 0).attr("x2", w)
        .attr("y1", vy).attr("y2", vy)
        .attr("stroke", "#15803d")
        .attr("stroke-width", 2.5);

      g.append("text")
        .attr("x", 4).attr("y", vy - 5)
        .attr("fill", "#15803d")
        .attr("font-size", 10).attr("font-weight", "600")
        .text(`Vacc ${fmt(vaccPct)}%`);
    }
  }, [data, vaccPct, herdThreshold, width, height]);

  return (
    <div>
      <svg ref={svgRef} width={width} height={height} className="overflow-visible" />
      {/* Legend */}
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-px w-5 bg-red-500" style={{ height: 2 }} />
          Cases (left axis)
        </span>
        {vaccPct != null && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 bg-green-700" style={{ height: 2 }} />
            Vacc rate (right axis) — survey snapshot
          </span>
        )}
        {herdThreshold != null && (
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block w-5"
              style={{
                height: 2,
                background:
                  "repeating-linear-gradient(90deg,#d97706 0,#d97706 5px,transparent 5px,transparent 9px)",
              }}
            />
            Herd threshold
          </span>
        )}
      </div>
      {vaccPct != null && (
        <p className="mt-1 text-[10px] text-slate-400 italic">
          Vaccination rate is a fixed survey snapshot, not a time series.
        </p>
      )}
    </div>
  );
}
