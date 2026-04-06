"use client";

interface LegendProps {
  colorScale: (value: number) => string;
  domain: [number, number];
}

const STEPS = 5;

export default function Legend({ colorScale, domain }: LegendProps) {
  const [min, max] = domain;
  const step = (max - min) / STEPS;
  const stops = Array.from({ length: STEPS + 1 }, (_, i) =>
    Math.round(min + i * step)
  );

  return (
    <div className="flex items-center gap-2 text-xs text-slate-600">
      <span>0</span>
      <div className="flex h-3 w-48 overflow-hidden rounded">
        {stops.slice(0, -1).map((v, i) => (
          <div
            key={i}
            style={{ backgroundColor: colorScale(v + step / 2), flex: 1 }}
          />
        ))}
      </div>
      <span>{max.toLocaleString()}</span>
      <span className="ml-1 text-slate-400">cases</span>
    </div>
  );
}
