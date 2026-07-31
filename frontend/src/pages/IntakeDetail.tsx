import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../lib/api";
import type { IntakeDetail } from "../lib/api";
import { Badge, Button, Card, ErrorNote, Spinner } from "../components/ui";

export default function IntakeDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<IntakeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.oc
      .intake(Number(id))
      .then(setData)
      .catch(() => setError("Couldn’t load this upload."));
  }, [id]);

  async function copy(url: string, awb: string) {
    await navigator.clipboard.writeText(url);
    setCopied(awb);
    setTimeout(() => setCopied(null), 1500);
  }

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!data) return <Spinner label="Loading…" />;

  const { intake, awbs } = data;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/orders" className="text-sm font-semibold text-ink-muted hover:text-ink">
          ← Upload history
        </Link>
        <h1 className="mt-2 text-xl font-bold">Upload #{intake.id}</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {intake.uploaded_at} · {intake.awb_count} AWBs · {intake.piece_count} pieces
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <a
          href={api.oc.uploadUrl(intake.id)}
          className="inline-flex items-center rounded-xl bg-nv-red px-4 py-2.5 text-sm font-semibold text-white hover:bg-nv-red-dark"
        >
          Download OC upload file
        </a>
        <a
          href={api.oc.linksUrl(intake.id)}
          className="inline-flex items-center rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-semibold hover:bg-canvas-soft"
        >
          Download link map (.csv)
        </a>
      </div>

      {intake.error_summary && (
        <ErrorNote>
          <strong>Skipped rows:</strong> {intake.error_summary}
        </ErrorNote>
      )}

      <Card className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
              <tr>
                <th className="px-4 py-3">AWB</th>
                <th className="px-4 py-3">Pharmacy</th>
                <th className="px-4 py-3">City</th>
                <th className="px-4 py-3 text-right">Koli</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Courier link</th>
              </tr>
            </thead>
            <tbody>
              {awbs.map((a) => (
                <tr key={a.awb_id} className="border-t border-line">
                  <td className="px-4 py-3"><span className="awb-chip">{a.awb_id}</span></td>
                  <td className="px-4 py-3">{a.pharmacy_name}</td>
                  <td className="px-4 py-3 text-ink-muted">{a.city ?? "—"}</td>
                  <td className="px-4 py-3 text-right">{a.koli}</td>
                  <td className="px-4 py-3">
                    <Badge tone={a.status === "created" ? "neutral" : "info"}>{a.status}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 whitespace-nowrap">
                      <a
                        href={a.courier_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-semibold text-nv-red hover:underline"
                      >
                        Open
                      </a>
                      <Button
                        variant="quiet"
                        className="px-2 py-1 text-xs"
                        onClick={() => copy(a.courier_url, a.awb_id)}
                      >
                        {copied === a.awb_id ? "Copied" : "Copy"}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
