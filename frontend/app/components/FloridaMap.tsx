"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import type { GeoPermissibleObjects } from "d3";
import type { FeatureCollection, Feature, Geometry } from "geojson";
import Tooltip from "./Tooltip";
import Legend from "./Legend";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CountyFeatureProps {
  NAME: string;        // county name
  [key: string]: unknown;
}

// The Plotly GeoJSON stores the 5-digit FIPS as a top-level `id` field,
// not inside `properties`.
type CountyFeature = Feature<Geometry, CountyFeatureProps> & { id: string };

interface TooltipState {
  x: number;
  y: number;
  county: string;
  value: number | null;
}

export type LayerMode = "cases" | "vaccination";

interface FloridaMapProps {
  casesByFips: Map<string, number>;
  vaccinationByFips: Map<string, number>;
  layerMode: LayerMode;
  onCountyClick: (fips: string, name: string) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FL_GEOJSON_URL =
  "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json";

const WIDTH = 800;
const HEIGHT = 540;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FloridaMap({
  casesByFips,
  vaccinationByFips,
  layerMode,
  onCountyClick,
}: FloridaMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [colorScale, setColorScale] = useState<(v: number) => string>(
    () => () => "#e2e8f0"
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
        const fl: FeatureCollection = {
          ...raw,
          features: raw.features.filter((f) => {
            const fips = (f as CountyFeature).id;
            return fips?.startsWith("12");
          }),
        };
        setGeojson(fl);
      })
      .catch(console.error);
    return () => { cancelled = true; };
  }, []);

  // ------------------------------------------------------------------
  // Rebuild colour scale when data or layer changes
  // ------------------------------------------------------------------
  useEffect(() => {
    if (layerMode === "vaccination") {
      const values = Array.from(vaccinationByFips.values());
      const min = values.length ? Math.min(...values) : 0;
      const max = values.length ? Math.max(...values) : 100;
      const scale = d3.scaleSequential(d3.interpolateGreens).domain([min, max]);
      setColorScale(() => (v: number) => scale(v));
      setDomain([min, max]);
    } else {
      const values = Array.from(casesByFips.values());
      const max = values.length ? Math.max(...values) : 1;
      const scale = d3.scaleSequential(d3.interpolateReds).domain([0, max]);
      setColorScale(() => (v: number) => scale(v));
      setDomain([0, max]);
    }
  }, [casesByFips, vaccinationByFips, layerMode]);

  // ------------------------------------------------------------------
  // Render / re-render map
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!geojson || !svgRef.current) return;

    const activeMap = layerMode === "vaccination" ? vaccinationByFips : casesByFips;

    const svg = d3.select(svgRef.current);
    const projection = d3.geoAlbersUsa().fitSize(
      [WIDTH, HEIGHT],
      geojson as GeoPermissibleObjects
    );
    const path = d3.geoPath().projection(projection);

    svg
      .selectAll<SVGPathElement, CountyFeature>("path.county")
      .data(geojson.features as CountyFeature[], (d) => d.id)
      .join("path")
      .attr("class", "county")
      .attr("d", (d) => path(d) ?? "")
      .attr("fill", (d) => {
        const v = activeMap.get(d.id);
        return v !== undefined ? colorScale(v) : "#e2e8f0";
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
          value: activeMap.get(d.id) ?? null,
        });
      })
      .on("mouseleave", () => setTooltip(null))
      .on("click", (_event: MouseEvent, d: CountyFeature) => {
        onCountyClick(d.id, d.properties.NAME);
      });
  }, [geojson, casesByFips, vaccinationByFips, layerMode, colorScale, onCountyClick]);

  const legendLabel = layerMode === "vaccination" ? "Vaccination %" : "Cases";

  return (
    <div className="relative w-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full rounded-xl bg-slate-50 shadow-inner"
        aria-label="Florida county disease map"
      />
      {tooltip && (
        <Tooltip
          x={tooltip.x}
          y={tooltip.y}
          county={tooltip.county}
          cases={layerMode === "cases" ? tooltip.value : null}
          vaccPct={layerMode === "vaccination" ? tooltip.value : null}
        />
      )}
      <div className="mt-2 flex justify-end">
        <Legend colorScale={colorScale} domain={domain} label={legendLabel} />
      </div>
    </div>
  );
}
