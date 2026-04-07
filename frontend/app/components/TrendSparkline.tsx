"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { TrendPoint } from "@/app/lib/api";

interface Props {
  data: TrendPoint[];
  vaccPct?: number | null;
  herdThreshold?: number | null;
  width?: number;
  height?: number;
}

function fmt(v: number): string {
  return v % 1 === 0 ? String(v) : v.toFixed(1);
}

const LABEL_MIN_GAP = 18; // px between two labels before we start nudging

/**
 * Given two desired y positions for labels, return adjusted positions
 * that are guaranteed to be at least LABEL_MIN_GAP apart.
 * The pair is shifted symmetrically around their midpoint.
 */
function separateLabels(ya: number, yb: number): [number, number] {
  const gap = Math.abs(ya - yb);
  if (gap >= LABEL_MIN_GAP) return [ya, yb];
  const mid = (ya + yb) / 2;
  const half = LABEL_MIN_GAP / 2;
  // keep relative order
  return ya <= yb
    ? [mid - half, mid + half]
    : [mid + half, mid - half];
}

export default function TrendSparkline({
  data,
  vaccPct,
  herdThreshold,
  width = 292,
  height = 190,
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

    // Tighten right-axis domain so lines sit mid-chart, not in the top sliver
    const vaccValues = [vaccPct, herdThreshold].filter((v): v is number => v != null);
    const spread = vaccValues.length >= 2
      ? Math.max(10, Math.abs(vaccValues[0] - vaccValues[1]) * 2)
      : 12;
    const vaccCenter = vaccValues.length
      ? vaccValues.reduce((a, b) => a + b, 0) / vaccValues.length
      : 85;
    const vaccMin = Math.max(0, vaccCenter - spread);
    const vaccMax = Math.min(100, vaccCenter + spread);

    const yRight = d3.scaleLinear().domain([vaccMin, vaccMax]).range([h, 0]);

    // ── Grid lines ───────────────────────────────────────────────────────────

    g.append("g")
      .call(d3.axisLeft(yLeft).ticks(4).tickSize(-w).tickFormat(() => ""))
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
          return n >= 1000 ? `${fmt(n / 1000)}k` : fmt(n);
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

    // Build X tick values: auto ticks + always include the last data point,
    // dropping any auto tick that falls within 20px of the last date.
    const lastDate = parsed[parsed.length - 1].date;
    const lastPx   = xScale(lastDate);
    const autoTicks = xScale.ticks(Math.min(parsed.length, 5));
    const filteredTicks = autoTicks.filter(
      (t) => Math.abs(xScale(t) - lastPx) > 20
    );
    const tickValues = [...filteredTicks, lastDate];

    g.append("g")
      .attr("transform", `translate(0,${h})`)
      .call(
        d3.axisBottom(xScale)
          .tickValues(tickValues)
          .tickFormat(d3.timeFormat("%b '%y") as (v: Date | d3.NumberValue) => string)
      )
      .call((ag) => ag.select(".domain").attr("stroke", "#cbd5e1"))
      .call((ag) => {
        // Bold + red the last tick so it stands out
        ag.selectAll(".tick text")
          .attr("fill", "#475569")
          .attr("font-size", 11);
        ag.selectAll(".tick:last-child text")
          .attr("fill", "#ef4444")
          .attr("font-weight", "700");
      })
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

    // ── Vacc/herd lines with non-overlapping labels ───────────────────────────

    const rawHerdY  = herdThreshold != null ? yRight(herdThreshold) : null;
    const rawVaccY  = vaccPct       != null ? yRight(vaccPct)        : null;

    // Separate labels so they never overlap
    let labelHerdY = rawHerdY;
    let labelVaccY = rawVaccY;

    if (rawHerdY != null && rawVaccY != null) {
      [labelHerdY, labelVaccY] = separateLabels(rawHerdY, rawVaccY);
    }

    // Draw herd threshold — label on LEFT side
    if (herdThreshold != null && rawHerdY != null) {
      g.append("line")
        .attr("x1", 0).attr("x2", w)
        .attr("y1", rawHerdY).attr("y2", rawHerdY)
        .attr("stroke", "#d97706")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "6,4");

      g.append("text")
        .attr("x", 4).attr("y", (labelHerdY ?? rawHerdY) - 4)
        .attr("fill", "#d97706")
        .attr("font-size", 12).attr("font-weight", "700")
        .text(`Herd ${fmt(herdThreshold)}%`);
    }

    // Draw vaccination rate — label on RIGHT side (text-anchor end)
    if (vaccPct != null && rawVaccY != null) {
      g.append("line")
        .attr("x1", 0).attr("x2", w)
        .attr("y1", rawVaccY).attr("y2", rawVaccY)
        .attr("stroke", "#15803d")
        .attr("stroke-width", 2.5);

      g.append("text")
        .attr("x", w - 4).attr("y", (labelVaccY ?? rawVaccY) - 4)
        .attr("text-anchor", "end")
        .attr("fill", "#15803d")
        .attr("font-size", 12).attr("font-weight", "700")
        .text(`Vacc ${fmt(vaccPct)}%`);
    }

    // ── Interactive hover overlay ─────────────────────────────────────────────

    const bisectDate = d3.bisector((d: { date: Date }) => d.date).left;

    // Hover elements (hidden by default)
    const hoverGroup = g.append("g").attr("class", "hover").style("display", "none");

    hoverGroup.append("line")
      .attr("class", "hover-line")
      .attr("y1", 0).attr("y2", h)
      .attr("stroke", "#94a3b8")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3");

    hoverGroup.append("circle")
      .attr("class", "hover-dot")
      .attr("r", 4)
      .attr("fill", "#ef4444")
      .attr("stroke", "#fff")
      .attr("stroke-width", 2);

    // Tooltip box (group with rect + two text lines)
    const tipGroup = hoverGroup.append("g").attr("class", "tip");

    const tipRect = tipGroup.append("rect")
      .attr("rx", 4)
      .attr("fill", "#1e293b")
      .attr("opacity", 0.88);

    const tipDate = tipGroup.append("text")
      .attr("fill", "#94a3b8")
      .attr("font-size", 10)
      .attr("font-weight", "500");

    const tipValue = tipGroup.append("text")
      .attr("fill", "#fca5a5")
      .attr("font-size", 12)
      .attr("font-weight", "700");

    // Invisible overlay rect to capture mouse events
    g.append("rect")
      .attr("width", w).attr("height", h)
      .attr("fill", "none")
      .style("pointer-events", "all")
      .on("mousemove", function (event: MouseEvent) {
        const [mx] = d3.pointer(event, this);
        const x0 = xScale.invert(mx);
        const idx = bisectDate(parsed, x0, 1);
        const d0 = parsed[idx - 1];
        const d1 = parsed[idx];
        const pt =
          !d1 || (x0.valueOf() - d0.date.valueOf() < d1.date.valueOf() - x0.valueOf())
            ? d0
            : d1;

        const px = xScale(pt.date);
        const py = yLeft(pt.value);

        hoverGroup.style("display", null);
        hoverGroup.select(".hover-line").attr("x1", px).attr("x2", px);
        hoverGroup.select(".hover-dot").attr("cx", px).attr("cy", py);

        const dateStr = pt.date.toLocaleDateString("en-US", {
          month: "short",
          year: "numeric",
        });
        const valStr = pt.value.toLocaleString();

        tipDate.attr("x", 0).attr("y", 0).text(dateStr);
        tipValue.attr("x", 0).attr("y", 13).text(`${valStr} cases`);

        // Measure text to size the rect
        const dateW = (tipDate.node() as SVGTextElement).getBBox().width;
        const valW  = (tipValue.node() as SVGTextElement).getBBox().width;
        const boxW  = Math.max(dateW, valW) + 12;
        const boxH  = 30;

        // Keep tooltip on screen
        let tipX = px + 8;
        if (tipX + boxW > w) tipX = px - boxW - 8;
        const tipY = Math.max(0, py - boxH / 2);

        tipGroup.attr("transform", `translate(${tipX},${tipY})`);
        tipRect.attr("x", -2).attr("y", -2).attr("width", boxW).attr("height", boxH);
        tipDate.attr("x", 4);
        tipValue.attr("x", 4);
      })
      .on("mouseleave", () => hoverGroup.style("display", "none"));
  }, [data, vaccPct, herdThreshold, width, height]);

  return (
    <div>
      <svg ref={svgRef} width={width} height={height} className="overflow-visible" />
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-5 bg-red-500" style={{ height: 2 }} />
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
