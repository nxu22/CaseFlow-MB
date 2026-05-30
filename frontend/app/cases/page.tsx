"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, ChevronRight, AlertCircle } from "lucide-react";
import { getCases, type Case, type CaseStatus } from "@/lib/api";

// 状态 → 颜色 / 文案 的映射，让列表一眼能区分案件阶段
const STATUS_STYLES: Record<CaseStatus, string> = {
  OPEN: "bg-blue-50 text-blue-700",
  IN_PROGRESS: "bg-amber-50 text-amber-700",
  CLOSED_WON: "bg-green-50 text-green-700",
  CLOSED_LOST: "bg-red-50 text-red-700",
  CLOSED_DISMISSED: "bg-slate-100 text-slate-600",
};
const STATUS_LABELS: Record<CaseStatus, string> = {
  OPEN: "Open",
  IN_PROGRESS: "In Progress",
  CLOSED_WON: "Won",
  CLOSED_LOST: "Lost",
  CLOSED_DISMISSED: "Dismissed",
};

function fmtDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function CasesPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCases()
      .then(setCases)
      .catch(() => setError("Failed to load cases"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-xl p-4 text-sm">
        <AlertCircle className="h-5 w-5" />
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Briefcase className="h-6 w-6 text-slate-400" />
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Cases</h1>
          <p className="text-sm text-slate-500">
            {cases.length} case{cases.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {cases.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm">
            No cases found
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50 text-left">
                <th className="px-4 py-3 font-medium text-slate-500">Case #</th>
                <th className="px-4 py-3 font-medium text-slate-500">Violation</th>
                <th className="px-4 py-3 font-medium text-slate-500">Status</th>
                <th className="px-4 py-3 font-medium text-slate-500">Court Date</th>
                <th className="px-4 py-3 font-medium text-slate-500">Fine</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr
                  key={c.id}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition"
                >
                  <td className="px-4 py-3 font-mono font-medium text-slate-900">
                    {c.case_number}
                  </td>
                  <td className="px-4 py-3 text-slate-600 max-w-[220px] truncate">
                    {c.violation_type}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[c.status]}`}
                    >
                      {STATUS_LABELS[c.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {fmtDate(c.court_date)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {c.fine_amount
                      ? `$${parseFloat(c.fine_amount).toFixed(0)}`
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/cases/${c.id}`}
                      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium transition"
                    >
                      View <ChevronRight className="h-4 w-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
