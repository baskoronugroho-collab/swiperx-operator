import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "../lib/api";
import type { OcCreateResult, OcPreview, Service } from "../lib/api";
import { Badge, Button, Card, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

const today = () => new Date().toISOString().slice(0, 10);

/** FR-OC1 — three explicit steps: (1) pick service + upload TMP, (2) preview what the
 *  engine parsed, (3) commit and download. Services are shown BY NAME; the S1/S2/S3
 *  codes are internal and never rendered. */
export default function OrderCreation() {
  const [services, setServices] = useState<Service[]>([]);
  const [service, setService] = useState("");
  const [deliveryDate, setDeliveryDate] = useState(today());
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<OcPreview | null>(null);
  const [result, setResult] = useState<OcCreateResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "create" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.oc
      .services()
      .then((r) => {
        setServices(r.services);
        setService((s) => s || r.services[0]?.code || "");
      })
      .catch(() => setError("Couldn’t load the service list."));
  }, []);

  const chosen = useMemo(() => services.find((s) => s.code === service), [services, service]);

  function reset() {
    setPreview(null);
    setResult(null);
    setError(null);
  }

  function pickFile(f: File | null) {
    setFile(f);
    reset();
  }

  async function runPreview() {
    if (!file || !service) return;
    setBusy("preview");
    setError(null);
    try {
      setPreview(await api.oc.preview(service, file));
    } catch (err) {
      setPreview(null);
      setError(describe(err));
    } finally {
      setBusy(null);
    }
  }

  async function runCreate() {
    if (!file || !service) return;
    setBusy("create");
    setError(null);
    try {
      setResult(await api.oc.create(service, file, deliveryDate));
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(null);
    }
  }

  /* FR-OC5 — all-or-nothing: any row error blocks the commit entirely. */
  const blocked = !!preview && preview.error_count > 0;

  if (result) return <CreateSuccess result={result} onAnother={() => { pickFile(null); if (fileInput.current) fileInput.current.value = ""; }} />;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Order creation</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Upload the SwipeRx TMP, check what was parsed, then create the orders and download the
          file to upload into Ninja’s system.
        </p>
      </header>

      <Card>
        <Step n={1} title="Choose the service and upload the TMP" />
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="Service">
            <select
              className={inputClass}
              value={service}
              onChange={(e) => {
                setService(e.target.value);
                reset();
              }}
            >
              {services.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>

          {/* "Pickup date" since 10 Aug 2026 — the day Ninja collects from the SwipeRx
              warehouse, which is what the DE actually schedules. It writes to col S
              (delivery_start_date) and that is correct, not a compromise: the forward
              upload template has no pickup_date column at all, so col S is the only date
              field on it. Returns carry both, set to the same day, matching the template. */}
          <Field label="Pickup date" hint="A single day — not a range.">
            <input
              type="date"
              className={inputClass}
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
            />
          </Field>
        </div>

        {chosen && (
          <div className="mt-4 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3">
            <ReadOnly label="Shipper ID" value={chosen.shipper_id ?? "—"} />
            <ReadOnly label="Shipper name" value={chosen.shipper_name ?? "—"} />
            <ReadOnly label="Corporate branch" value={chosen.branch_id ?? "—"} />
          </div>
        )}

        <div className="mt-4">
          <Field label="SwipeRx TMP file" hint="The .xlsx batch file exported from SwipeRx.">
            <input
              ref={fileInput}
              type="file"
              accept=".xlsx,.xlsm"
              className={`${inputClass} file:mr-3 file:rounded-lg file:border-0 file:bg-canvas-soft file:px-3 file:py-1.5 file:text-sm file:font-semibold`}
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            />
          </Field>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <Button onClick={runPreview} disabled={!file || busy !== null}>
            {busy === "preview" ? "Checking…" : "Check file"}
          </Button>
          {busy === "preview" && <Spinner />}
        </div>

        {error && <div className="mt-4"><ErrorNote>{error}</ErrorNote></div>}
      </Card>

      {preview && (
        <Card>
          <Step n={2} title="Check what was parsed" />

          <div className="mt-4 flex flex-wrap gap-2">
            <Stat label="AWBs" value={preview.awb_count} />
            <Stat label="Pieces" value={preview.piece_count} />
            <Stat label="Errors" value={preview.error_count} tone={preview.error_count ? "danger" : "ok"} />
          </div>

          {blocked && (
            <div className="mt-4 space-y-3">
              <ErrorNote>
                <strong>{preview.error_count} row{preview.error_count === 1 ? "" : "s"} failed validation.</strong>{" "}
                Nothing is created while any row is invalid — fix the file and upload it again.
              </ErrorNote>
              <div className="max-h-64 overflow-auto rounded-xl border border-line">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                    <tr>
                      <th className="px-3 py-2">Row</th>
                      <th className="px-3 py-2">AWB</th>
                      <th className="px-3 py-2">Problem</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.errors.map((e, i) => (
                      <tr key={i} className="border-t border-line">
                        <td className="px-3 py-2 text-ink-muted">{e.row ?? "—"}</td>
                        <td className="px-3 py-2 font-mono text-xs">{e.awb ?? "—"}</td>
                        <td className="px-3 py-2">{e.error}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!blocked && preview.awbs.length > 0 && (
            <div className="mt-4 max-h-80 overflow-auto rounded-xl border border-line">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                  <tr>
                    <th className="px-3 py-2">AWB</th>
                    <th className="px-3 py-2">Pharmacy</th>
                    <th className="px-3 py-2">City</th>
                    <th className="px-3 py-2 text-right">POs</th>
                    <th className="px-3 py-2 text-right">Koli</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.awbs.map((a) => (
                    <tr key={a.awb_id} className="border-t border-line">
                      <td className="px-3 py-2"><span className="awb-chip">{a.awb_id}</span></td>
                      <td className="px-3 py-2">{a.pharmacy_name}</td>
                      <td className="px-3 py-2 text-ink-muted">{a.city ?? "—"}</td>
                      <td className="px-3 py-2 text-right">{a.po_count}</td>
                      <td className="px-3 py-2 text-right">{a.collies}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-5 border-t border-line pt-5">
            <Step n={3} title="Create the orders" />
            <p className="mt-1 text-sm text-ink-muted">
              This creates {preview.awb_count} AWB{preview.awb_count === 1 ? "" : "s"}, each with its
              own courier link, and generates the two files to download.
            </p>
            <div className="mt-4 flex items-center gap-3">
              <Button onClick={runCreate} disabled={blocked || busy !== null}>
                {busy === "create" ? "Creating…" : "Create orders"}
              </Button>
              {busy === "create" && <Spinner />}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function CreateSuccess({ result, onAnother }: { result: OcCreateResult; onAnother: () => void }) {
  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-start gap-4">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-ok-soft text-ok">
            ✓
          </div>
          <div className="flex-1">
            <h1 className="text-lg font-bold">
              {result.awb_count} order{result.awb_count === 1 ? "" : "s"} created
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              {result.piece_count} piece{result.piece_count === 1 ? "" : "s"}. Each AWB has its own
              courier link, already injected into the delivery-instruction column.
            </p>

            <div className="mt-5 flex flex-wrap gap-3">
              <a
                href={api.oc.uploadUrl(result.intake_id)}
                className="inline-flex items-center rounded-xl bg-nv-red px-4 py-2.5 text-sm font-semibold text-white hover:bg-nv-red-dark"
              >
                Download OC upload file
              </a>
              <a
                href={api.oc.linksUrl(result.intake_id)}
                className="inline-flex items-center rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-semibold hover:bg-canvas-soft"
              >
                Download link map (.csv)
              </a>
            </div>

            <p className="mt-4 text-sm text-ink-muted">
              Next: upload the OC file into Ninja’s internal system.
            </p>

            {result.warning && (
              <div className="mt-4 rounded-xl border border-warn/25 bg-warn-soft px-4 py-3 text-sm text-warn">
                <strong>Delivery instruction was trimmed.</strong> {result.warning} The RDO text
                plus the link exceeded the 500-character limit on that column.
              </div>
            )}

            {result.links.length > 0 && (
              <div className="mt-6">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h2 className="text-sm font-bold">Courier links created</h2>
                  <button
                    onClick={() =>
                      navigator.clipboard.writeText(
                        result.links.map((l) => `${l.awb_id}\t${l.pharmacy_name}\t${l.url}`).join("\n"),
                      )
                    }
                    className="text-xs font-semibold text-nv-red hover:underline"
                  >
                    Copy all
                  </button>
                </div>
                <div className="max-h-72 overflow-auto rounded-xl border border-line">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-canvas-soft text-left text-xs uppercase text-ink-muted">
                      <tr>
                        <th className="px-3 py-2">AWB</th>
                        <th className="px-3 py-2">Pharmacy</th>
                        <th className="px-3 py-2">Link</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.links.map((l) => (
                        <tr key={l.awb_id} className="border-t border-line">
                          <td className="px-3 py-2"><span className="awb-chip">{l.awb_id}</span></td>
                          <td className="px-3 py-2">{l.pharmacy_name}</td>
                          <td className="px-3 py-2">
                            <a
                              href={l.url}
                              target="_blank"
                              rel="noreferrer"
                              className="font-mono text-[11px] text-nv-red hover:underline"
                            >
                              {l.url}
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {result.error_count > 0 && (
              <div className="mt-5">
                <ErrorNote>
                  {result.error_count} row{result.error_count === 1 ? " was" : "s were"} skipped:{" "}
                  {result.errors.map((e) => e.error).join("; ")}
                </ErrorNote>
              </div>
            )}

            <div className="mt-6 flex gap-3">
              <Button variant="ghost" onClick={onAnother}>
                Create another
              </Button>
              <Link
                to={`/orders/${result.intake_id}`}
                className="inline-flex items-center rounded-xl px-4 py-2.5 text-sm font-semibold text-ink-muted hover:text-ink"
              >
                View this upload
              </Link>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function Step({ n, title }: { n: number; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid h-6 w-6 place-items-center rounded-full bg-ink text-xs font-bold text-white">
        {n}
      </span>
      <h2 className="font-bold">{title}</h2>
    </div>
  );
}

function ReadOnly({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-canvas-soft px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="mt-0.5 text-sm font-semibold">{value}</div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "ok" | "danger" }) {
  return (
    <div className="rounded-xl border border-line px-4 py-2">
      <span className="text-xs text-ink-muted">{label}</span>{" "}
      {tone ? (
        <Badge tone={tone}>{value}</Badge>
      ) : (
        <span className="font-bold">{value}</span>
      )}
    </div>
  );
}

function describe(err: unknown): string {
  if (!(err instanceof ApiError)) return "Something went wrong. Try again.";
  const map: Record<string, string> = {
    empty_file: "That file is empty.",
    unknown_service: "Unknown service — reload the page and pick again.",
    no_valid_awbs: "No valid AWBs were found in this file.",
    bad_delivery_date: "The pickup date isn’t valid.",
    all_awbs_already_exist:
      "Every AWB in this file already exists, so nothing was created. Note that re-uploading "
      + "a corrected file does NOT update an existing AWB — it is skipped.",
  };
  if (map[err.detail]) return map[err.detail];
  if (err.status === 422)
    return `The file couldn’t be read as a TMP for this service. ${err.detail}`;
  if (err.status === 403) return "Your account can’t create orders.";
  return err.detail || "Something went wrong.";
}
