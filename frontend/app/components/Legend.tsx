"use client";

interface LegendProps {
  colorScale: (value: number) => string;
  domain: [number, number];
  label?: string;
  thresholdPct?: number;
}

const STEPS = 5;

export default function Legend({ colorScale, domain, label = "cases", thresholdPct }: LegendProps) {
  const [min, max] = domain;
  const step = (max - min) / STEPS;
  const stops = Array.from({ length: STEPS + 1 }, (_, i) =>
    Math.round(min + i * step)
  );

  const maxLabel = label === "Vaccination %" ? `${max.toFixed(1)}%` : max.toLocaleString();
  const minLabel = label === "Vaccination %" ? `${min.toFixed(1)}%` : "0";

  const markerLeft =
    thresholdPct !== undefined && max > min
      ? Math.max(0, Math.min(100, ((thresholdPct - min) / (max - min)) * 100))
      : null;

  return (
    <div className="flex items-center gap-2 text-xs text-slate-600">
      <span>{minLabel}</span>
      <div className="relative flex h-3 w-48 overflow-visible rounded">
        <div className="flex h-full w-full overflow-hidden rounded">
          {stops.slice(0, -1).map((v, i) => (
            <div
              key={i}
              style={{ backgroundColor: colorScale(v + step / 2), flex: 1 }}
            />
          ))}
        </div>
        {markerLeft !== null && (
          <div
            className="absolute top-0 h-full"
            style={{ left: `${markerLeft}%` }}
          >
            <div className="h-full w-0.5 bg-amber-500" />
            <span
              className="absolute -bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap text-amber-600 font-semibold"
              style={{ fontSize: 9 }}
            >
              Herd
            </span>
          </div>
        )}
      </div>
      <span>{maxLabel}</span>
      <span className="ml-1 text-slate-400">{label}</span>
    </div>
  );
}
