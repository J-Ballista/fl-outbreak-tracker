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
  NAME: string;
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
export type AlertSeverity = "watch" | "warning" | "emergency";

interface FloridaMapProps {
  casesByFips: Map<string, number>;
  vaccinationByFips: Map<string, number>;
  alertsByFips: Map<string, AlertSeverity>;
  layerMode: LayerMode;
  /** Safe religious-exemption ceiling = (100 - herd_threshold) - medical_contraindication_pct */
  safeExemptThreshold?: number | null;
  onCountyClick: (fips: string, name: string) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FL_GEOJSON_URL =
  "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json";

const WIDTH = 800;
const HEIGHT = 540;

const ALERT_COLORS: Record<AlertSeverity, string> = {
  watch: "#f59e0b",
  warning: "#f97316",
  emergency: "#ef4444",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FloridaMap({
  casesByFips,
  vaccinationByFips,
  alertsByFips,
  layerMode,
  safeExemptThreshold = 5,
  onCountyClick,
}: FloridaMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [colorScale, setColorScale] = useState<(v: number) => string>(
    () => () => "#e2e8f0"
  );
  const [domain, setDomain] = useState<[number, number]>([0, 1]);
  const [thresholdPct, setThresholdPct] = useState<number>(90);

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
    return () => {
      cancelled = true;
    };
  }, []);

  // ------------------------------------------------------------------
  // Rebuild colour scale when data or layer changes
  // ------------------------------------------------------------------
  useEffect(() => {
    if (layerMode === "vaccination") {
      const values = Array.from(vaccinationByFips.values());
      const dataMax = values.length ? Math.max(...values) : 20;
      // Domain: 0 → max exemption; ensure at least 5% wide so low-exemption
      // counties still show variation rather than all appearing white.
      const hi = Math.max(dataMax, 5);
      const scale = d3.scaleSequential(d3.interpolateOrRd).domain([0, hi]);
      setColorScale(() => (v: number) => scale(v));
      setDomain([0, hi]);
      // Threshold marker: safe exemption ceiling already computed upstream
      setThresholdPct(safeExemptThreshold ?? 5);
    } else {
      const values = Array.from(casesByFips.values());
      const max = values.length ? Math.max(...values) : 1;
      const scale = d3.scaleSequential(d3.interpolateReds).domain([0, max]);
      setColorScale(() => (v: number) => scale(v));
      setDomain([0, max]);
    }
  }, [casesByFips, vaccinationByFips, layerMode, safeExemptThreshold]);

  // ------------------------------------------------------------------
  // Render / re-render map
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!geojson || !svgRef.current) return;

    const activeMap = layerMode === "vaccination" ? vaccinationByFips : casesByFips;

    const svg = d3.select(svgRef.current);
    const projection = d3
      .geoAlbersUsa()
      .fitSize([WIDTH, HEIGHT], geojson as GeoPermissibleObjects);
    const path = d3.geoPath().projection(projection);

    // County fill paths
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

    // Alert ring overlays — drawn on top of county fills
    const alertFeatures = (geojson.features as CountyFeature[]).filter(
      (f) => alertsByFips.has(f.id)
    );

    svg
      .selectAll<SVGPathElement, CountyFeature>("path.alert-ring")
      .data(alertFeatures, (d) => d.id)
      .join("path")
      .attr("class", "alert-ring")
      .attr("d", (d) => path(d) ?? "")
      .attr("fill", "none")
      .attr("stroke", (d) => ALERT_COLORS[alertsByFips.get(d.id)!])
      .attr("stroke-width", 2.5)
      .style("pointer-events", "none");

    // Pulsing dot for emergency counties
    const emergencyFeatures = (geojson.features as CountyFeature[]).filter(
      (f) => alertsByFips.get(f.id) === "emergency"
    );

    svg
      .selectAll<SVGCircleElement, CountyFeature>("circle.alert-dot")
      .data(emergencyFeatures, (d) => d.id)
      .join("circle")
      .attr("class", "alert-dot")
      .attr("cx", (d) => {
        const centroid = path.centroid(d);
        return centroid[0] ?? 0;
      })
      .attr("cy", (d) => {
        const centroid = path.centroid(d);
        return centroid[1] ?? 0;
      })
      .attr("r", 5)
      .attr("fill", ALERT_COLORS.emergency)
      .attr("opacity", 0.85)
      .style("pointer-events", "none");
  }, [geojson, casesByFips, vaccinationByFips, alertsByFips, layerMode, colorScale, onCountyClick]);

  const legendLabel = layerMode === "vaccination" ? "Exemption %" : "Cases";

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
          exemptPct={layerMode === "vaccination" ? tooltip.value : null}
        />
      )}
      <div className="mt-4 flex justify-end">
        <Legend
          colorScale={colorScale}
          domain={domain}
          label={legendLabel}
          thresholdPct={layerMode === "vaccination" ? thresholdPct : undefined}
        />
      </div>
      {/* Alert legend */}
      {alertsByFips.size > 0 && (
        <div className="absolute bottom-10 left-3 flex flex-col gap-1 rounded-lg bg-white/90 px-3 py-2 shadow-md ring-1 ring-slate-200 text-xs">
          <span className="font-semibold text-slate-600 mb-1">Alerts</span>
          {(["emergency", "warning", "watch"] as AlertSeverity[]).map((sev) => (
            <div key={sev} className="flex items-center gap-1.5">
              <span
                className="inline-block h-3 w-3 rounded-full border-2"
                style={{ borderColor: ALERT_COLORS[sev] }}
              />
              <span className="capitalize text-slate-600">{sev}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
