"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import type { GeoPermissibleObjects } from "d3";
import type { FeatureCollection, Feature, Geometry } from "geojson";
import Tooltip from "./Tooltip";
import Legend from "./Legend";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CountyFeatureProps {
  GEOID: string;       // 5-digit FIPS
  NAME: string;        // county name
  [key: string]: unknown;
}

type CountyFeature = Feature<Geometry, CountyFeatureProps>;

interface TooltipState {
  x: number;
  y: number;
  county: string;
  cases: number | null;
}

interface FloridaMapProps {
  /** Map from FIPS code → total case count for the selected filters */
  casesByFips: Map<string, number>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// US Census TIGER GeoJSON — Florida counties only (FIPS state 12)
const FL_GEOJSON_URL =
  "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json";

const WIDTH = 800;
const HEIGHT = 540;

// Colour scale: white → deep red
const COLOR_RANGE: [string, string] = ["#fff5f0", "#a50f15"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FloridaMap({ casesByFips }: FloridaMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [colorScale, setColorScale] = useState<(v: number) => string>(
    () => () => COLOR_RANGE[0]
  );
  const [domain, setDomain] = useState<[number, number]>([0, 1]);

  // ------------------------------------------------------------------
  // Load GeoJSON once
  // ------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    fetch(FL_GEOJSON_URL)
      .then((r) => r.json())
      .then((raw: FeatureCollection) => {
        if (cancelled) return;
        // Filter to Florida counties only (FIPS starts with "12")
        const fl: FeatureCollection = {
          ...raw,
          features: raw.features.filter((f) => {
            const props = f.properties as CountyFeatureProps;
            return props?.GEOID?.startsWith("12");
          }),
        };
        setGeojson(fl);
      })
      .catch(console.error);
    return () => { cancelled = true; };
  }, []);

  // ------------------------------------------------------------------
  // Build colour scale whenever case data changes
  // ------------------------------------------------------------------
  useEffect(() => {
    const values = Array.from(casesByFips.values());
    const max = values.length ? Math.max(...values) : 1;
    const scale = d3.scaleSequential(d3.interpolateReds).domain([0, max]);
    setColorScale(() => (v: number) => scale(v));
    setDomain([0, max]);
  }, [casesByFips]);

  // ------------------------------------------------------------------
  // Render / re-render map
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!geojson || !svgRef.current) return;

    const svg = d3.select(svgRef.current);

    // Fit projection to Florida's bounding box
    const projection = d3.geoAlbersUsa().fitSize(
      [WIDTH, HEIGHT],
      geojson as GeoPermissibleObjects
    );
    const path = d3.geoPath().projection(projection);

    // Draw / update county paths
    svg
      .selectAll<SVGPathElement, CountyFeature>("path.county")
      .data(geojson.features as CountyFeature[], (d) => d.properties.GEOID)
      .join("path")
      .attr("class", "county")
      .attr("d", (d) => path(d) ?? "")
      .attr("fill", (d) => {
        const count = casesByFips.get(d.properties.GEOID);
        return count !== undefined ? colorScale(count) : "#e2e8f0";
      })
      .attr("stroke", "#94a3b8")
      .attr("stroke-width", 0.5)
      .style("cursor", "pointer")
      .on("mousemove", (event: MouseEvent, d: CountyFeature) => {
        const [mx, my] = d3.pointer(event, svgRef.current!);
        setTooltip({
          x: mx,
          y: my,
          county: `${d.properties.NAME} County`,
          cases: casesByFips.get(d.properties.GEOID) ?? null,
        });
      })
      .on("mouseleave", () => setTooltip(null));
  }, [geojson, casesByFips, colorScale]);

  return (
    <div className="relative w-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full rounded-xl bg-slate-50 shadow-inner"
        aria-label="Florida county disease case map"
      />
      {tooltip && (
        <Tooltip
          x={tooltip.x}
          y={tooltip.y}
          county={tooltip.county}
          cases={tooltip.cases}
        />
      )}
      <div className="mt-2 flex justify-end">
        <Legend colorScale={colorScale} domain={domain} />
      </div>
    </div>
  );
}
