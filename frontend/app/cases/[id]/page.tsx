"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Upload,
  FileText,
  Sparkles,
  Download,
  Calendar,
  DollarSign,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import {
  getCase,
  getDocuments,
  uploadDocument,
  summarizeDocument,
  getDownloadUrl,
  type Case,
  type Document,
  type DocumentType,
  type CaseStatus,
} from "@/lib/api";

const STATUS_STYLES: Record<CaseStatus, string> = {
  OPEN: "bg-blue-50 text-blue-700",
  IN_PROGRESS: "bg-amber-50 text-amber-700",
  CLOSED_WON: "bg-green-50 text-green-700",
  CLOSED_LOST: "bg-red-50 text-red-700",
  CLOSED_DISMISSED: "bg-slate-100 text-slate-600",
};

function fmtDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("en-CA", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// Next.js 16：params 是 Promise。客户端组件用 React 19 的 use() 解包。
export default function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [docType, setDocType] = useState<DocumentType>("other");
  const [summarizingId, setSummarizingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([getCase(id), getDocuments(id)])
      .then(([c, docs]) => {
        setCaseData(c);
        setDocuments(docs);
      })
      .catch(() => setError("Case not found"))
      .finally(() => setLoading(false));
  }, [id]);

  // 上传：选文件 → 传后端(进 S3 + 写库) → 把新文档插到列表最前
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const doc = await uploadDocument(id, file, docType);
      setDocuments((prev) => [doc, ...prev]);
    } catch {
      alert("Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // 摘要：调后端 → 后端从 S3 取文件喂给 Claude → 返回更新后的文档
  const handleSummarize = async (doc: Document) => {
    setSummarizingId(doc.id);
    try {
      const updated = await summarizeDocument(id, doc.id);
      setDocuments((prev) =>
        prev.map((d) => (d.id === updated.id ? updated : d))
      );
    } catch {
      alert("Failed to generate summary");
    } finally {
      setSummarizingId(null);
    }
  };

  // 下载：换取有时效的 presigned URL，新标签页打开
  const handleDownload = async (doc: Document) => {
    try {
      const { download_url } = await getDownloadUrl(id, doc.id);
      window.open(download_url, "_blank");
    } catch {
      alert("Failed to get download link");
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }
  if (error || !caseData) {
    return (
      <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-xl p-4 text-sm">
        <AlertCircle className="h-5 w-5" />
        {error ?? "Case not found"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 返回 + 标题 */}
      <div>
        <Link
          href="/cases"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 transition mb-3"
        >
          <ArrowLeft className="h-4 w-4" /> All cases
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900 font-mono">
            {caseData.case_number}
          </h1>
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[caseData.status]}`}
          >
            {caseData.status.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      {/* 案件信息卡 */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">
          Case Details
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-slate-400 mb-0.5">Violation</p>
            <p className="text-sm font-medium text-slate-900">
              {caseData.violation_type}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400 mb-0.5">Violation Date</p>
            <p className="text-sm text-slate-900">
              {fmtDate(caseData.violation_date)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400 mb-0.5 flex items-center gap-1">
              <Calendar className="h-3 w-3" /> Court Date
            </p>
            <p className="text-sm font-medium text-slate-900">
              {fmtDate(caseData.court_date)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400 mb-0.5 flex items-center gap-1">
              <DollarSign className="h-3 w-3" /> Fine
            </p>
            <p className="text-sm text-slate-900">
              {caseData.fine_amount
                ? `$${parseFloat(caseData.fine_amount).toFixed(2)}`
                : "—"}
            </p>
          </div>
          {caseData.description && (
            <div className="col-span-2 sm:col-span-3">
              <p className="text-xs text-slate-400 mb-0.5">Description</p>
              <p className="text-sm text-slate-600">{caseData.description}</p>
            </div>
          )}
        </div>
      </div>

      {/* 文档区 */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Documents ({documents.length})
          </h2>
          <div className="flex items-center gap-2">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentType)}
              className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 text-slate-600 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ticket">Ticket</option>
              <option value="court_notice">Court Notice</option>
              <option value="evidence">Evidence</option>
              <option value="defense_letter">Defense Letter</option>
              <option value="other">Other</option>
            </select>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-medium rounded-lg transition"
            >
              {uploading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Upload className="h-3.5 w-3.5" />
              )}
              Upload
            </button>
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleUpload}
              accept=".pdf,.jpg,.jpeg,.png,.txt"
              className="hidden"
            />
          </div>
        </div>

        {documents.length === 0 ? (
          <div className="py-10 text-center text-slate-400 text-sm border-2 border-dashed border-slate-200 rounded-xl">
            <FileText className="h-8 w-8 mx-auto mb-2 text-slate-300" />
            No documents yet. Upload a ticket, notice, or evidence file.
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="border border-slate-200 rounded-xl p-4 hover:border-slate-300 transition"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <FileText className="h-5 w-5 text-slate-400 flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {doc.filename}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5 capitalize">
                        {doc.document_type.replace(/_/g, " ")} ·{" "}
                        {(doc.file_size / 1024).toFixed(0)} KB
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleDownload(doc)}
                      title="Download"
                      className="p-1.5 text-slate-400 hover:text-blue-600 rounded-lg hover:bg-blue-50 transition"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleSummarize(doc)}
                      disabled={summarizingId === doc.id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 hover:border-blue-300 hover:text-blue-700 hover:bg-blue-50 disabled:opacity-50 transition"
                    >
                      {summarizingId === doc.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : doc.ai_summary ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <Sparkles className="h-3.5 w-3.5 text-blue-500" />
                      )}
                      {summarizingId === doc.id
                        ? "Summarizing…"
                        : doc.ai_summary
                        ? "Re-summarize"
                        : "AI Summary"}
                    </button>
                  </div>
                </div>

                {doc.ai_summary && (
                  <div className="mt-3 pl-8">
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 mb-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-blue-500" />
                        AI Summary
                      </div>
                      <p className="text-sm text-slate-700 leading-relaxed">
                        {doc.ai_summary}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
