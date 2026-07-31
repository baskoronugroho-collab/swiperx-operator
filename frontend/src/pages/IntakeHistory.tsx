import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import type { Intake, Service } from "../lib/api";
import { Badge, Card, EmptyState, ErrorNote, Spinner } from "../components/ui";

/** FR-OC6 — history of successful uploads with both generated files kept for
 *  re-download and audit. */
export default function IntakeHistory() {
  const [intakes, setIntakes] = useState<Intake[] | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.oc.intakes(), api.oc.services()])
      .then(([i, s]) => {
        setIntakes(i.intakes);
        setServices(s.services);
      })
      .catch(() => setError("Couldn’t load the upload history."));
  }, []);

  const serviceName = (code: string) => services.find((s) => s.code === code)?.name ?? code;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Upload history</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Every successful order creation, with the generated files kept for re-download.
        </p>
      </header>

      {error && <ErrorNote>{error}</ErrorNote>}
      {!intakes && !error && <Spinner label="Loading…" />}

      {intakes && intakes.length === 0 && (
        <EmptyState title="No uploads yet" body="Created batches will appear here." />
      )}

      {intakes && intakes.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                <tr>
                  <th className="px-4 py-3">Uploaded</th>
                  <th className="px-4 py-3">Service</th>
                  <th className="px-4 py-3 text-right">AWBs</th>
                  <th className="px-4 py-3 text-right">Pieces</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Files</th>
                </tr>
              </thead>
              <tbody>
                {intakes.map((i) => (
                  <tr key={i.id} className="border-t border-line hover:bg-canvas-soft/60">
                    <td className="px-4 py-3">
                      <Link to={`/orders/${i.id}`} className="font-semibold text-nv-red hover:underline">
                        {i.uploaded_at}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{serviceName(i.service_code)}</td>
                    <td className="px-4 py-3 text-right">{i.awb_count}</td>
                    <td className="px-4 py-3 text-right">{i.piece_count}</td>
                    <td className="px-4 py-3">
                      <Badge tone={i.status === "created" ? "ok" : "warn"}>{i.status}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-3 whitespace-nowrap">
                        <a href={api.oc.uploadUrl(i.id)} className="text-xs font-semibold text-nv-red hover:underline">
                          OC file
                        </a>
                        <a href={api.oc.linksUrl(i.id)} className="text-xs font-semibold text-nv-red hover:underline">
                          Links
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
