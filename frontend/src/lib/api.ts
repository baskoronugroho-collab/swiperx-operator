/** Typed client for the FastAPI backend.
 *
 * Session auth is an httpOnly cookie (`swiperx_session`), so every request goes
 * same-origin with credentials — dev proxies /api through Vite for the same reason.
 * Courier routes under /api/c/<token> are deliberately unauthenticated: the token IS
 * the credential, so they must never send or require a session.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin", ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) detail = body.detail.map((d: never) => JSON.stringify(d)).join("; ");
    } catch {
      /* non-JSON error body — keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T,>(path: string) => request<T>(path);
const postJson = <T,>(path: string, body: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
const postForm = <T,>(path: string, form: FormData) =>
  request<T>(path, { method: "POST", body: form });

/* ---------------------------------------------------------------- types ---- */

export type Role =
  | "superadmin"
  | "program_manager"
  | "de"
  | "implant"
  | "station_ic"
  | "validator"
  | "swiperx";

export interface User {
  id: number;
  email: string;
  name: string;
  roles: Role[];
  has_access: boolean;
}

export interface VersionInfo {
  name: string;
  env: string;
  changelog: { version: string; notes: string; released_at: string }[];
  /** Which sign-in methods the deployment actually has configured. */
  auth: { google: boolean; dev_login: boolean };
}

export interface Service {
  code: string;
  name: string;
  direction: "forward" | "return";
  branch_id?: string;
  service_level?: string;
  shipper_id?: string;
  shipper_name?: string;
}

export interface OcRowError {
  row: number | null;
  awb: string | null;
  error: string;
}

export interface AwbPreview {
  awb_id: string;
  pharmacy_name: string;
  city: string | null;
  collies: number;
  po_count: number;
  pieces: number;
  is_return: boolean;
}

export interface OcPreview {
  service: string;
  awb_count: number;
  piece_count: number;
  error_count: number;
  errors: OcRowError[];
  awbs: AwbPreview[];
}

export interface CreatedLink {
  awb_id: string;
  pharmacy_name: string;
  city: string | null;
  koli: number;
  url: string;
}

export interface OcCreateResult {
  intake_id: number;
  service: string;
  awb_count: number;
  piece_count: number;
  error_count: number;
  errors: OcRowError[];
  /** Set when col-R RDO text had to be trimmed to fit the 500-char cap. */
  warning: string | null;
  links: CreatedLink[];
  upload_url: string;
  links_url: string;
}

export interface CourierLink {
  awb_id: string;
  pharmacy_name: string;
  city: string | null;
  koli: number;
  status: string;
  is_return: boolean;
  service_id: string;
  intake_id: number | null;
  created_at: string;
  courier_url: string;
}

export interface Intake {
  id: number;
  service_code: string;
  awb_count: number;
  piece_count: number;
  row_count: number;
  status: string;
  uploaded_at: string;
}

export interface IntakeDetail {
  intake: Intake & { error_summary: string | null };
  awbs: {
    awb_id: string;
    pharmacy_name: string;
    city: string | null;
    koli: number;
    is_return: boolean;
    status: string;
    courier_url: string;
  }[];
}

/* ------------------------------------------------------------ courier ----- */

export interface PoLine {
  po_number: string;
  koli: number;
}

export interface CourierOrder {
  awb_id: string;
  merchant_order_number: string | null;
  pharmacy_name: string;
  address: string | null;
  city: string | null;
  service_id: string;
  status: string;
  is_return: boolean;
  invoice: string | null;
  item_detail: string | null;
  po_lines: PoLine[];
  /* capture state — lets a returning link resume in place (PRD §7.2.2) */
  captures: CourierCapture[];
  expired: boolean;
  terminal: boolean;
  fail_reasons: { code: FailReason; id: string; en: string }[];
}

export interface Gate {
  outcome: Outcome;
  complete: boolean;
  missing: string[];
}

export type Outcome = "delivered" | "reject";

export interface CourierCapture {
  id: number;
  doc_type: DocType;
  po_number: string | null;
  photo_url: string;
  signed_stamped: boolean | null;
  captured_at: string;
}

export type DocType =
  | "pharmacy_pod"
  | "receiver_pod"
  | "delivery_note"
  | "sp_manual"
  | "rejected_goods"
  | "awb_sticker"
  | "return_form";

export type FailReason =
  | "cancelled"
  | "not_ordered"
  | "address_wrong"
  | "moved"
  | "no_receiver"
  | "reschedule"
  | "office_closed"
  | "force_majeure"
  | "refused_sign";

export interface CourierSubmitResult {
  status: string;
  return_flagged: boolean;
  return_awbs: string[];
}

/* -------------------------------------------------------------- returns --- */

export interface RejectReturn {
  id: number;
  original_awb_id: string;
  pharmacy_name: string;
  city: string | null;
  service_id: string;
  return_type: "sebagian" | "semua";
  rejected_at: string;
  acknowledged_at: string | null;
  acknowledged_by_email: string | null;
  return_tids: string | null;
  tids_sent_at: string | null;
  tids_sent_by_email: string | null;
  stage: "pending_ack" | "acknowledged" | "tids_sent";
  proof_photos: { doc_type: DocType; photo_url: string }[];
}

/* ------------------------------------------------------------------ api --- */

export interface ManagedUser {
  id: number;
  name: string;
  google_email: string;
  active: boolean;
  roles: Role[];
}

export const ALL_ROLES: Role[] = [
  "superadmin", "program_manager", "de", "implant", "station_ic", "validator", "swiperx",
];

export const api = {
  version: () => get<VersionInfo>("/api/version"),

  auth: {
    me: () => get<User>("/api/auth/me"),
    /** Stopgap until the Google OAuth client exists; the user must already be seeded
     *  and active, and DEV_LOGIN_ENABLED must be on. Sets the session cookie only —
     *  call `me()` afterwards for the identity. */
    devLogin: (email: string) =>
      postJson<{ ok: boolean; roles: Role[] }>("/api/auth/dev-login", { email }),
    googleLoginUrl: () => "/api/auth/google/login",
    logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  },

  users: {
    list: () => get<{ users: ManagedUser[] }>("/api/users"),
    register: (email: string, name: string, roles: Role[]) =>
      postJson<{ id: number; email: string; roles: Role[] }>("/api/users", { email, name, roles }),
    update: (id: number, patch: { roles?: Role[]; active?: boolean }) =>
      request<{ id: number; roles: Role[] }>(`/api/users/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      }),
  },

  oc: {
    services: () => get<{ services: Service[] }>("/api/oc/services"),
    preview: (service: string, file: File) => {
      const fd = new FormData();
      fd.append("service", service);
      fd.append("file", file);
      return postForm<OcPreview>("/api/oc/preview", fd);
    },
    create: (service: string, file: File, deliveryDate?: string) => {
      const fd = new FormData();
      fd.append("service", service);
      fd.append("file", file);
      if (deliveryDate) fd.append("delivery_date", deliveryDate);
      return postForm<OcCreateResult>("/api/oc/create", fd);
    },
    links: (q?: string) =>
      get<{ links: CourierLink[]; count: number }>(
        `/api/oc/links${q ? `?q=${encodeURIComponent(q)}` : ""}`,
      ),
    intakes: () => get<{ intakes: Intake[] }>("/api/oc/intakes"),
    intake: (id: number) => get<IntakeDetail>(`/api/oc/intakes/${id}`),
    uploadUrl: (id: number) => `/api/oc/intakes/${id}/upload.xlsx`,
    linksUrl: (id: number) => `/api/oc/intakes/${id}/links.csv`,
  },

  courier: {
    order: (token: string) => get<CourierOrder>(`/api/c/${token}/order`),
    upload: (token: string, docType: DocType, blob: Blob, opts: {
      poNumber?: string;
      signedStamped?: boolean;
      timestampSource: "camera" | "exif";
      gps?: string;
    }) => {
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("file", blob, `${docType}.jpg`);
      fd.append("timestamp_source", opts.timestampSource);
      if (opts.poNumber) fd.append("po_number", opts.poNumber);
      if (opts.signedStamped !== undefined) fd.append("signed_stamped", String(opts.signedStamped));
      if (opts.gps) fd.append("gps", opts.gps);
      return postForm<CourierCapture>(`/api/c/${token}/capture`, fd);
    },
    deleteCapture: (token: string, captureId: number) =>
      request<void>(`/api/c/${token}/capture/${captureId}`, { method: "DELETE" }),
    attest: (token: string, captureId: number, signedStamped: boolean) =>
      request<{ id: number; signed_stamped: boolean }>(`/api/c/${token}/capture/${captureId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signed_stamped: signedStamped }),
      }),
    gate: (token: string, outcome: Outcome) => get<Gate>(`/api/c/${token}/gate?outcome=${outcome}`),
    submit: (token: string, body: { outcome: Outcome; return_type?: "sebagian" | "semua" }) =>
      postJson<CourierSubmitResult>(`/api/c/${token}/submit`, body),
    fail: (token: string, body: { fail_reason: FailReason; reason_note?: string; gps?: string }) =>
      postJson<CourierSubmitResult>(`/api/c/${token}/fail`, body),
  },

  returns: {
    list: (stage?: string) =>
      get<{ returns: RejectReturn[] }>(`/api/returns${stage ? `?stage=${stage}` : ""}`),
    acknowledge: (id: number, acknowledged: boolean) =>
      postJson<RejectReturn>(`/api/returns/${id}/acknowledge`, { acknowledged }),
    sendTids: (id: number, returnTids: string) =>
      postJson<RejectReturn>(`/api/returns/${id}/tids`, { return_tids: returnTids }),
    exportUrl: () => "/api/returns/export.csv",
  },
};
