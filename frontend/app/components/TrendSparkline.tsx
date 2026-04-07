"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { TrendPoint } from "@/app/lib/api";

interface Props {
  data: TrendPoint[];
  vaccPct?: number | null;        // current vaccination rate 0–100 (green line)
  herdThreshold?: number | null;  // recommended threshold 0–100 (dotted line)
  width?: number;
  height?: number;
}

export default function TrendSparkline({
  data,
  vaccPct,
  herdThreshold,
  width = 292,
  height = 160,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const hasVacc = vaccPct != null || herdThreshold != null;
    const margin = {
      top: 12,
      right: hasVacc ? 44 : 12,
      bottom: 28,
      left: 40,
    };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    if (data.length === 0) {
      g.append("text")
        .attr("x", w / 2)
        .attr("y", h / 2)
        .attr("text-anchor", "middle")
        .attr("fill", "#94a3b8")
        .attr("font-size", 11)
        .text("No data for selected filters");
      return;
    }

    const parsed = data.map((d) => ({
      date: new Date(d.report_date),
      value: d.total_cases,
    }));

    // ── Scales ──────────────────────────────────────────────────────────────

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(parsed, (d) => d.date) as [Date, Date])
      .range([0, w]);

    const maxCases = d3.max(parsed, (d) => d.value) ?? 1;
    const yLeft = d3
      .scaleLinear()
      .domain([0, maxCases * 1.1])
      .range([h, 0])
      .nice();

    const yRight = d3
      .scaleLinear()
      .domain([0, 100])
      .range([h, 0]);

    // ── Grid lines ───────────────────────────────────────────────────────────

    g.append("g")
      .attr("class", "grid")
      .call(
        d3
          .axisLeft(yLeft)
          .ticks(4)
          .tickSize(-w)
          .tickFormat(() => "")
      )
      .call((ag) => ag.select(".domain").remove())
      .call((ag) =>
        ag
          .selectAll(".tick line")
          .attr("stroke", "#e2e8f0")
          .attr("stroke-dasharray", "2,3")
      );

    // ── Axes ─────────────────────────────────────────────────────────────────

    // Left — case counts
    g.append("g")
      .call(
        d3
          .axisLeft(yLeft)
          .ticks(4)
          .tickFormat((v) => {
            const n = Number(v);
            return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
          })
      )
      .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
      .call((ag) =>
        ag
          .selectAll(".tick text")
          .attr("fill", "#64748b")
          .attr("font-size", 9)
      )
      .call((ag) =>
        ag.selectAll(".tick line").attr("stroke", "#cbd5e1")
      );

    // Left axis label
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -h / 2)
      .attr("y", -32)
      .attr("text-anchor", "middle")
      .attr("fill", "#ef4444")
      .attr("font-size", 9)
      .text("Cases");

    // Right — vaccination % (only when relevant)
    if (hasVacc) {
      g.append("g")
        .attr("transform", `translate(${w},0)`)
        .call(
          d3
            .axisRight(yRight)
            .ticks(5)
            .tickFormat((v) => `${v}%`)
        )
        .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
        .call((ag) =>
          ag
            .selectAll(".tick text")
            .attr("fill", "#64748b")
            .attr("font-size", 9)
        )
        .call((ag) =>
          ag.selectAll(".tick line").attr("stroke", "#cbd5e1")
        );

      // Right axis label
      g.append("text")
        .attr("transform", "rotate(90)")
        .attr("x", h / 2)
        .attr("y", -(w + 36))
        .attr("text-anchor", "middle")
        .attr("fill", "#15803d")
        .attr("font-size", 9)
        .text("Vacc %");
    }

    // Bottom X axis
    g.append("g")
      .attr("transform", `translate(0,${h})`)
      .call(
        d3
          .axisBottom(xScale)
          .ticks(4)
          .tickFormat(d3.timeFormat("%b '%y") as (v: Date | d3.NumberValue) => string)
      )
      .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
      .call((ag) =>
        ag
          .selectAll(".tick text")
          .attr("fill", "#64748b")
          .attr("font-size", 9)
      )
      .call((ag) =>
        ag.selectAll(".tick line").attr("stroke", "#cbd5e1")
      );

    // ── Case area + line (red) ───────────────────────────────────────────────

    const area = d3
      .area<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y0(h)
      .y1((d) => yLeft(d.value))
      .curve(d3.curveMonotoneX);

    const line = d3
      .line<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y((d) => yLeft(d.value))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(parsed)
      .attr("fill", "rgba(239,68,68,0.12)")
      .attr("d", area);

    g.append("path")
      .datum(parsed)
      .attr("fill", "none")
      .attr("stroke", "#ef4444")
      .attr("stroke-width", 2)
      .attr("d", line);

    // ── Herd-threshold dotted line (amber) ────────────────────────────────────

    if (herdThreshold != null && hasVacc) {
      const ty = yRight(herdThreshold);
      g.append("line")
        .attr("x1", 0)
        .attr("x2", w)
        .attr("y1", ty)
        .attr("y2", ty)
        .attr("stroke", "#f59e0b")
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "5,4");

      g.append("text")
        .attr("x", w - 2)
        .attr("y", ty - 3)
        .attr("text-anchor", "end")
        .attr("fill", "#f59e0b")
        .attr("font-size", 8)
        .text(`Herd ${herdThreshold}%`);
    }

    // ── Current vaccination rate horizontal line (dark green) ─────────────────

    if (vaccPct != null && hasVacc) {
      const vy = yRight(vaccPct);
      g.append("line")
        .attr("x1", 0)
        .attr("x2", w)
        .attr("y1", vy)
        .attr("y2", vy)
        .attr("stroke", "#15803d")
        .attr("stroke-width", 2);

      g.append("text")
        .attr("x", w - 2)
        .attr("y", vy - 3)
        .attr("text-anchor", "end")
        .attr("fill", "#15803d")
        .attr("font-size", 8)
        .text(`Vacc ${vaccPct.toFixed(1)}%`);
    }
  }, [data, vaccPct, herdThreshold, width, height]);

  return (
    <div>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="overflow-visible"
      />
      {/* Legend */}
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 rounded bg-red-500" />
          Cases
        </span>
        {vaccPct != null && (
          <span className="flex items-center gap-1">
            <span className="inline-block h-0.5 w-4 rounded bg-green-700" />
            Vacc rate
          </span>
        )}
        {herdThreshold != null && (
          <span className="flex items-center gap-1">
            <span
              className="inline-block h-0.5 w-4 rounded"
              style={{
                background:
                  "repeating-linear-gradient(90deg,#f59e0b 0,#f59e0b 4px,transparent 4px,transparent 8px)",
              }}
            />
            Herd threshold
          </span>
        )}
      </div>
    </div>
  );
}
