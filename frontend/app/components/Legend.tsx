"use client";

interface LegendProps {
  colorScale: (value: number) => string;
  domain: [number, number];
  label?: string;
}

const STEPS = 5;

export default function Legend({ colorScale, domain, label = "cases" }: LegendProps) {
  const [min, max] = domain;
  const step = (max - min) / STEPS;
  const stops = Array.from({ length: STEPS + 1 }, (_, i) =>
    Math.round(min + i * step)
  );

  const maxLabel = label === "Vaccination %" ? `${max.toFixed(1)}%` : max.toLocaleString();
  const minLabel = label === "Vaccination %" ? `${min.toFixed(1)}%` : "0";

  return (
    <div className="flex items-center gap-2 text-xs text-slate-600">
      <span>{minLabel}</span>
      <div className="flex h-3 w-48 overflow-hidden rounded">
        {stops.slice(0, -1).map((v, i) => (
          <div
            key={i}
            style={{ backgroundColor: colorScale(v + step / 2), flex: 1 }}
          />
        ))}
      </div>
      <span>{maxLabel}</span>
      <span className="ml-1 text-slate-400">{label}</span>
    </div>
  );
}
