"use client";

interface TooltipProps {
  x: number;
  y: number;
  county: string;
  cases: number | null;
}

export default function Tooltip({ x, y, county, cases }: TooltipProps) {
  return (
    <div
      className="pointer-events-none absolute z-50 rounded-lg bg-slate-900 px-3 py-2 text-sm text-white shadow-lg"
      style={{ left: x + 12, top: y - 10 }}
    >
      <p className="font-semibold">{county}</p>
      <p className="text-slate-300">
        {cases !== null ? `${cases.toLocaleString()} cases` : "No data"}
      </p>
    </div>
  );
}
