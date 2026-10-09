import type { RejectReturn } from "../lib/api";

/** The expanded Detail panel for one reject return: door evidence photos and the trail.
 *  Same content as the panel on Reject returns, kept as its own component so the Vasil
 *  page can show it without touching that page. */
export default function ReturnDetail({ row }: { row: RejectReturn }) {
  return (
    <div className="flex flex-wrap gap-6">
      {row.proof_photos.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase text-ink-muted">Door evidence</p>
          <div className="flex flex-wrap gap-2">
            {row.proof_photos.map((p, i) => (
              <a key={i} href={p.photo_url} target="_blank" rel="noreferrer">
                <img
                  src={p.photo_url}
                  alt={p.doc_type}
                  className="h-24 w-24 rounded-lg border border-line object-cover"
                />
              </a>
            ))}
          </div>
        </div>
      )}
      <div className="min-w-64 text-sm">
        <p className="mb-1.5 text-xs font-semibold uppercase text-ink-muted">Trail</p>
        <ul className="space-y-1 text-xs text-ink-muted">
          <li>Rejected {row.rejected_at} — {row.reject_pcs ?? "?"} pcs reported at the door</li>
          {row.validated_at && (
            <li>✓ Validated {row.validated_at} by {row.validated_by_email ?? "—"} (legacy step)</li>
          )}
          {row.de_uploaded_at && (
            <li>
              ✓ Return OC uploaded {row.de_uploaded_at} by {row.de_uploaded_by_email ?? "—"} —{" "}
              <span className="font-mono">{row.return_awb_id}</span>
            </li>
          )}
          {row.printed_at && (
            <li>✓ Printed &amp; labelled {row.printed_at} by {row.printed_by_email ?? "—"}</li>
          )}
          {row.rts_requested_at && (
            <li>
              ✓ RTS triggered on <span className="font-mono">{row.original_awb_id}</span>{" "}
              {row.rts_requested_at} by {row.rts_requested_by_email ?? "—"}
            </li>
          )}
          {row.flagged && (
            <li className="text-danger">
              ⚑ Flagged {row.flagged_at} by {row.flagged_by_email ?? "—"} — &ldquo;{row.flag_note}&rdquo;
            </li>
          )}
          {row.return_tids && <li>Legacy TIDs: <span className="font-mono">{row.return_tids}</span></li>}
        </ul>
      </div>
    </div>
  );
}
