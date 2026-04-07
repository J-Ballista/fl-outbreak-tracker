"use client";

import { useMemo } from "react";

interface MonthRangeSliderProps {
  dateFrom: string;   // ISO date string "YYYY-MM-DD" or ""
  dateTo: string;     // ISO date string "YYYY-MM-DD" or ""
  onChange: (from: string, to: string) => void;
}

// Build an array of the last 24 months ending with the current month
function buildMonths(): Array<{ label: string; value: string }> {
  const now = new Date();
  const months: Array<{ label: string; value: string }> = [];
  for (let i = 23; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const label = d.toLocaleString("default", { month: "short", year: "numeric" });
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    months.push({ label, value });
  }
  return months;
}

function lastDayOfMonth(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  const last = new Date(y, m, 0); // day 0 of next month = last day of this month
  return `${y}-${String(m).padStart(2, "0")}-${String(last.getDate()).padStart(2, "0")}`;
}

export default function MonthRangeSlider({
  dateFrom,
  dateTo,
  onChange,
}: MonthRangeSliderProps) {
  const months = useMemo(buildMonths, []);

  // Resolve current thumb positions from ISO date props
  const fromIdx = useMemo(() => {
    if (!dateFrom) return 0;
    const ym = dateFrom.slice(0, 7);
    const idx = months.findIndex((m) => m.value === ym);
    return idx >= 0 ? idx : 0;
  }, [dateFrom, months]);

  const toIdx = useMemo(() => {
    if (!dateTo) return months.length - 1;
    const ym = dateTo.slice(0, 7);
    const idx = months.findIndex((m) => m.value === ym);
    return idx >= 0 ? idx : months.length - 1;
  }, [dateTo, months]);

  function handleFrom(e: React.ChangeEvent<HTMLInputElement>) {
    const idx = Number(e.target.value);
    const newFrom = idx <= toIdx ? idx : toIdx;
    onChange(
      `${months[newFrom].value}-01`,
      lastDayOfMonth(months[toIdx].value)
    );
  }

  function handleTo(e: React.ChangeEvent<HTMLInputElement>) {
    const idx = Number(e.target.value);
    const newTo = idx >= fromIdx ? idx : fromIdx;
    onChange(
      `${months[fromIdx].value}-01`,
      lastDayOfMonth(months[newTo].value)
    );
  }

  return (
    <div className="flex flex-col gap-1 min-w-[260px]">
      <div className="flex items-center justify-between text-xs font-medium text-slate-600">
        <span>Date range</span>
        <span className="text-slate-500">
          {months[fromIdx].label} – {months[toIdx].label}
        </span>
      </div>

      {/* From slider */}
      <div className="relative flex items-center gap-2">
        <span className="w-12 shrink-0 text-xs text-slate-400 text-right">From</span>
        <input
          type="range"
          min={0}
          max={months.length - 1}
          value={fromIdx}
          onChange={handleFrom}
          className="w-full h-1.5 accent-blue-600 cursor-pointer"
        />
      </div>

      {/* To slider */}
      <div className="relative flex items-center gap-2">
        <span className="w-12 shrink-0 text-xs text-slate-400 text-right">To</span>
        <input
          type="range"
          min={0}
          max={months.length - 1}
          value={toIdx}
          onChange={handleTo}
          className="w-full h-1.5 accent-blue-600 cursor-pointer"
        />
      </div>
    </div>
  );
}
