"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { TrendPoint } from "@/app/lib/api";

interface Props {
  data: TrendPoint[];
  width?: number;
  height?: number;
}

export default function TrendSparkline({ data, width = 280, height = 56 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const margin = { top: 4, right: 4, bottom: 4, left: 4 };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    const parsed = data.map((d) => ({
      date: new Date(d.report_date),
      value: d.total_cases,
    }));

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(parsed, (d) => d.date) as [Date, Date])
      .range([0, w]);

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(parsed, (d) => d.value) ?? 1])
      .range([h, 0]);

    const area = d3
      .area<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y0(h)
      .y1((d) => yScale(d.value))
      .curve(d3.curveMonotoneX);

    const line = d3
      .line<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y((d) => yScale(d.value))
      .curve(d3.curveMonotoneX);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    g.append("path")
      .datum(parsed)
      .attr("fill", "rgba(59,130,246,0.15)")
      .attr("d", area);

    g.append("path")
      .datum(parsed)
      .attr("fill", "none")
      .attr("stroke", "#3b82f6")
      .attr("stroke-width", 1.5)
      .attr("d", line);
  }, [data, width, height]);

  if (data.length === 0) {
    return (
      <div
        style={{ width, height }}
        className="flex items-center justify-center text-xs text-slate-500"
      >
        No trend data
      </div>
    );
  }

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="overflow-visible"
    />
  );
}
