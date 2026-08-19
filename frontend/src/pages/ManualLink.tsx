/** Manual link builder — phase-1 field testing.
 *
 * Type the fields for one AWB, mint a courier link, then paste the generated col-R string
 * into the order's delivery instructions by hand in Ninja's system. The point is to put a
 * real link in front of a real driver before trusting the TMP intake path.
 *
 * It also answers the open question in OC_AWB_PARENT_CHECK §8 — what column A actually
 * accepts — since the parent TRID is typed rather than derived from a TMP.
 */
import { useEffect, useState } from "react";

import { api, ApiError } from "../lib/api";
import type { ManualLinkResult, ManualLinkRow, Service } from "../lib/api";
import { Awb, Badge, Button, Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "../components/ui";

type PoRow = { po_number: string; koli: number };

function CopyRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  const [done, setDone] = useState(false);
  return (
    <div className="border-t border-line py-3 first:border-t-0">
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <span className="text-[13px] font-semibold text-ink">{label}</span>
        <button
          onClick={async () => {
            await navigator.clipboard.writeText(value);
            setDone(true);
            setTimeout(() => setDone(false), 1400);
          }}
          className="shrink-0 text-xs font-semibold text-ink-muted hover:text-nv-red"
        >
          {done ? "Copied" : "Copy"}
        </button>
      </div>
      <p className={`break-all text-sm text-ink-muted ${mono ? "font-mono text-xs" : ""}`}>
        {value || <span className="italic">(blank)</span>}
      </p>
    </div>
  );
}

export default function ManualLink() {
  const [services, setServices] = useState<Service[]>([]);
  const [rows, setRows] = useState<ManualLinkRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ManualLinkResult | null>(null);

  const [service, setService] = useState("");
  const [awbId, setAwbId] = useState("");
  const [pharmacy, setPharmacy] = useState("Apotek Uji Coba");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [postcode, setPostcode] = useState("");
  const [phone, setPhone] = useState("");
  const [weight, setWeight] = useState("1");
  const [collies, setCollies] = useState(1);
  const [deliveryDate, setDeliveryDate] = useState("");
  const [pos, setPos] = useState<PoRow[]>([{ po_number: "", koli: 1 }]);

  async function refresh() {
    const r = await api.manual.list();
    setRows(r.links);
  }

  useEffect(() => {
    (async () => {
      try {
        const [s, l] = await Promise.all([api.oc.services(), api.manual.list()]);
        setServices(s.services);
        setService(s.services[0]?.code ?? "");
        setRows(l.links);
      } catch (e) {
        setError(e instanceof ApiError ? e.detail : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Mirrors oc_engine.piece_trids: one child per collie, prefixed with the PO that collie
  // belongs to, numbered continuously across the whole AWB. Previewed live so the operator
  // sees the exact AC string before anything is created. Falls back to the AWB as the prefix
  // only when no PO has been entered yet, which is what the backend does too.
  const preview: string[] = [];
  if (awbId.trim()) {
    const lines = pos.filter((p) => p.po_number.trim());
    if (lines.length === 0) {
      for (let i = 0; i < Math.max(1, collies); i++) {
        preview.push(`${awbId.trim()}-${String(i + 1).padStart(2, "0")}`);
      }
    } else {
      let n = 0;
      for (const p of lines) {
        for (let k = 0; k < Math.max(1, p.koli); k++) {
          n += 1;
          preview.push(`${p.po_number.trim()}-${String(n).padStart(2, "0")}`);
        }
      }
    }
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.manual.create({
        service,
        awb_id: awbId.trim(),
        pharmacy_name: pharmacy,
        address,
        city,
        postcode,
        phone,
        weight,
        collies,
        delivery_date: deliveryDate || undefined,
        po_lines: pos.filter((p) => p.po_number.trim()).map((p) => ({
          po_number: p.po_number.trim(),
          koli: p.koli,
        })),
      });
      setResult(res);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Loading…" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-xl font-bold">Manual link</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-muted">
          Build one courier link by hand, without a TMP file, then paste it into the order&rsquo;s
          delivery instructions in Ninja&rsquo;s system. The link it produces is a{" "}
          <strong className="font-semibold text-ink">real, working link</strong> — the driver app
          treats it exactly like one created from a batch. Use it for phase-1 testing, and for any
          one-off order that has no template.
        </p>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-display font-semibold">Order details</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Service">
              <select className={inputClass} value={service} onChange={(e) => setService(e.target.value)}>
                {services.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Pickup date" hint="Blank = today">
              <input
                type="date"
                className={inputClass}
                value={deliveryDate}
                onChange={(e) => setDeliveryDate(e.target.value)}
              />
            </Field>
            <Field
              label="Parent tracking number (col A)"
              hint="The SwipeAWB. Also goes in col D as the merchant order number."
            >
              <input
                className={inputClass}
                value={awbId}
                placeholder="AWB02U24V"
                onChange={(e) => setAwbId(e.target.value)}
              />
            </Field>
            <Field label="Total koli (col AB)">
              <input
                type="number"
                min={1}
                className={inputClass}
                value={collies}
                onChange={(e) => setCollies(Math.max(1, Number(e.target.value) || 1))}
              />
            </Field>
            <Field label="Pharmacy name">
              <input className={inputClass} value={pharmacy} onChange={(e) => setPharmacy(e.target.value)} />
            </Field>
            <Field label="Weight (col W)">
              <input className={inputClass} value={weight} onChange={(e) => setWeight(e.target.value)} />
            </Field>
            <Field label="Phone">
              <input className={inputClass} value={phone} onChange={(e) => setPhone(e.target.value)} />
            </Field>
            <Field label="City">
              <input className={inputClass} value={city} onChange={(e) => setCity(e.target.value)} />
            </Field>
            <Field label="Postcode">
              <input className={inputClass} value={postcode} onChange={(e) => setPostcode(e.target.value)} />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Address">
                <input className={inputClass} value={address} onChange={(e) => setAddress(e.target.value)} />
              </Field>
            </div>
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[13px] font-semibold text-ink">PO lines</span>
              <button
                onClick={() => setPos([...pos, { po_number: "", koli: 1 }])}
                className="text-xs font-semibold text-ink-muted hover:text-nv-red"
              >
                + Add PO
              </button>
            </div>
            <p className="mb-3 text-xs text-ink-muted">
              Shown to the courier behind the link and on the DN. Each PO also becomes the prefix
              of its own child pieces in col AC, numbered continuously across the AWB.
            </p>
            {/* Each input is sized by its WRAPPER, not by a width utility on the input
                itself. `inputClass` already carries w-full, so adding w-24 alongside it put
                two width utilities on one element — which of them wins is decided by their
                order in Tailwind's generated CSS, not by the order in the className string,
                so the koli box rendered full width and the row broke. (10 Aug 2026) */}
            <div className="flex gap-2 pr-7 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              <span className="min-w-0 flex-1">Nomor PO</span>
              <span className="w-24 shrink-0">Koli</span>
            </div>
            <div className="mt-1 space-y-2">
              {pos.map((p, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="min-w-0 flex-1">
                    <input
                      className={inputClass}
                      placeholder="26072713473538DTjozNXFa"
                      value={p.po_number}
                      onChange={(e) => {
                        const next = [...pos];
                        next[i] = { ...p, po_number: e.target.value };
                        setPos(next);
                      }}
                    />
                  </div>
                  <div className="w-24 shrink-0">
                    <input
                      type="number"
                      min={1}
                      className={inputClass}
                      value={p.koli}
                      onChange={(e) => {
                        const next = [...pos];
                        next[i] = { ...p, koli: Math.max(1, Number(e.target.value) || 1) };
                        setPos(next);
                      }}
                    />
                  </div>
                  <button
                    onClick={() => setPos(pos.filter((_, j) => j !== i))}
                    disabled={pos.length === 1}
                    aria-label={`Remove PO line ${i + 1}`}
                    className="w-5 shrink-0 text-sm font-semibold text-ink-muted transition hover:text-danger disabled:invisible"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Read-only. The auto/blank picker was removed 19 Aug 2026 — children are
              always written, one per koli, prefixed by their own PO. The blank-AC path
              still exists in the API for a future NV trial, just not as an operator choice. */}
          <div className="mt-5 rounded-xl border border-line bg-canvas-soft p-4">
            <p className="text-[13px] font-semibold text-ink">Child pieces (col AC)</p>
            <p className="mt-1 text-xs text-ink-muted">
              One per koli, prefixed by its own PO and numbered continuously across the AWB.
            </p>
            <p className="mt-2 break-all font-mono text-xs text-ink-muted">
              {preview.length ? preview.join(", ") : "— isi PO dulu —"}
            </p>
          </div>

          <Button className="mt-5 w-full" onClick={submit} disabled={busy || !awbId.trim() || !service}>
            {busy ? "Creating…" : "Create link"}
          </Button>
        </Card>

        <div className="space-y-6">
          {result ? (
            <Card>
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="font-display font-semibold">Paste into Ninja</h2>
                <Badge tone={result.instr_truncated ? "warn" : "ok"}>
                  col R {result.instr_length}/{result.instr_limit}
                </Badge>
              </div>
              {result.instr_truncated && (
                <div className="mb-3">
                  <ErrorNote>
                    The RDO wording was trimmed to fit 500 characters. Compliance text should never
                    be cut — shorten the link host or report this before using the row.
                  </ErrorNote>
                </div>
              )}
              <CopyRow label="Courier link" value={result.url} />
              <CopyRow
                label="R — delivery_instructions (paste this whole string)"
                value={result.delivery_instructions}
                mono
              />
              <CopyRow label="A — requested_tracking_number" value={result.upload_columns.A_requested_tracking_number} mono />
              <CopyRow label="D — merchant_order_number" value={result.upload_columns.D_merchant_order_number} mono />
              <CopyRow label="AB — total_quantity" value={result.upload_columns.AB_total_quantity} mono />
              <CopyRow label="AC — requested_piece_tracking_numbers" value={result.upload_columns.AC_piece_tracking_numbers} mono />
              <div className="mt-4 flex gap-2">
                <a href={api.manual.uploadUrl(result.awb_id)}>
                  <Button variant="ghost">Download 1-row .xlsx</Button>
                </a>
                <a href={result.url} target="_blank" rel="noreferrer">
                  <Button variant="ghost">Open as courier</Button>
                </a>
              </div>
            </Card>
          ) : (
            <EmptyState
              title="No link yet"
              body="Fill the form and create one. Everything you need to paste appears here."
            />
          )}

          <Card>
            <h2 className="mb-1 font-display font-semibold">Manually created links ({rows.length})</h2>
            <p className="mb-3 text-xs text-ink-muted">
              Links made here rather than from a batch. Deleting one frees its AWB number for reuse.
            </p>
            {rows.length === 0 ? (
              <p className="text-sm text-ink-muted">Nothing created yet.</p>
            ) : (
              <div className="space-y-2">
                {rows.map((r) => (
                  <div
                    key={r.awb_id}
                    className="flex items-center justify-between gap-3 border-t border-line py-2.5 first:border-t-0"
                  >
                    <div className="min-w-0">
                      <Awb>{r.awb_id}</Awb>
                      <p className="mt-1 truncate text-xs text-ink-muted">
                        {r.pharmacy_name} · {r.koli} koli · {r.status}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        onClick={() => navigator.clipboard.writeText(r.courier_url)}
                        className="text-xs font-semibold text-ink-muted hover:text-nv-red"
                      >
                        Copy
                      </button>
                      <button
                        onClick={async () => {
                          await api.manual.remove(r.awb_id);
                          await refresh();
                        }}
                        className="text-xs font-semibold text-ink-muted hover:text-danger"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
