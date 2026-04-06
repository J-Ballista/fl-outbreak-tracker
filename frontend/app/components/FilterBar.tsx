"use client";

import { Disease } from "@/app/lib/api";

interface FilterBarProps {
  diseases: Disease[];
  selectedDiseaseId: number | undefined;
  dateFrom: string;
  dateTo: string;
  onDiseaseChange: (id: number | undefined) => void;
  onDateFromChange: (d: string) => void;
  onDateToChange: (d: string) => void;
}

export default function FilterBar({
  diseases,
  selectedDiseaseId,
  dateFrom,
  dateTo,
  onDiseaseChange,
  onDateFromChange,
  onDateToChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl bg-white px-5 py-3 shadow-sm ring-1 ring-slate-200">
      {/* Disease picker */}
      <div className="flex items-center gap-2">
        <label
          htmlFor="disease-select"
          className="text-sm font-medium text-slate-600"
        >
          Disease
        </label>
        <select
          id="disease-select"
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={selectedDiseaseId ?? ""}
          onChange={(e) =>
            onDiseaseChange(
              e.target.value ? Number(e.target.value) : undefined
            )
          }
        >
          <option value="">All diseases</option>
          {diseases.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>

      {/* Date range */}
      <div className="flex items-center gap-2">
        <label htmlFor="date-from" className="text-sm font-medium text-slate-600">
          From
        </label>
        <input
          id="date-from"
          type="date"
          className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
        />
      </div>
      <div className="flex items-center gap-2">
        <label htmlFor="date-to" className="text-sm font-medium text-slate-600">
          To
        </label>
        <input
          id="date-to"
          type="date"
          className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={dateTo}
          onChange={(e) => onDateToChange(e.target.value)}
        />
      </div>
    </div>
  );
}
