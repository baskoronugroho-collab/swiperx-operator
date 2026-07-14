#!/usr/bin/env node
// SwipeRx OC intake engine — LOCAL TRIAL harness (Node, no deps).
// Reads a SwipeRx TMP batch (.xlsx), applies the rules in
// ../OC Template/OC_TEMPLATE_AND_ENGINE_GUIDE.md, and emits the NV upload CSV,
// a per-AWB courier-link CSV, and a summary.
//
// Usage:
//   node oc-engine.mjs --in <TMP.xlsx> --service S1|S2|S3 [--out <dir>] [--base-url <host>]
//
// This is a validation harness ONLY. The production engine ports these same rules
// into the FastAPI backend (DB persistence, real tokens, .xlsx output).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { readSheet, normNum } from './lib/xlsx-read.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ---- args ----
function parseArgs(argv) {
  const a = {};
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    if (k.startsWith('--')) { a[k.slice(2)] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true; }
  }
  return a;
}
const args = parseArgs(process.argv);
if (!args.in || !args.service) {
  console.error('Usage: node oc-engine.mjs --in <TMP.xlsx> --service S1|S2|S3 [--out <dir>] [--base-url <host>]');
  process.exit(2);
}
const service = String(args.service).toUpperCase();
const config = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
const svc = config.services[service];
if (!svc) { console.error('Unknown service ' + service + ' (expected S1|S2|S3)'); process.exit(2); }
const baseUrl = args['base-url'] || config.public_base_url;
const outDir = args.out ? path.resolve(args.out) : path.join(__dirname, 'out');
fs.mkdirSync(outDir, { recursive: true });

const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD (local trial: system date)

// ---- NV upload column order (A..AE forward, A..AJ return) ----
const FWD_COLS = [
  'requested_tracking_number', 'global_shipper_id', 'service_type', 'reference.merchant_order_number',
  'service_level', 'from.name', 'from.phone_number', 'from.address.address1', 'from.address.country',
  'to.name', 'to.phone_number', 'to.address.address1', 'to.address.country', 'to.address.kecamatan',
  'to.address.city', 'to.address.province', 'to.address.postcode', 'parcel_job.delivery_instructions',
  'parcel_job.delivery_start_date', 'parcel_job.delivery_timeslot.start_time', 'parcel_job.delivery_timeslot.end_time',
  'parcel_job.delivery_timeslot.timezone', 'parcel_job.dimensions.weight', 'parcel_job.is_pickup_required',
  'parcel_job.items.0.item_description', 'parcel_job.items.0.is_dangerous_good', 'b2b.documents_required',
  'bundle_information.total_quantity', 'bundle_information.requested_piece_tracking_numbers',
  'parcel_job.insured_value', 'corporate.branch_id',
];
const RET_EXTRA_COLS = [
  'parcel_job.pickup_date', 'parcel_job.pickup_timeslot.start_time', 'parcel_job.pickup_timeslot.end_time',
  'parcel_job.pickup_timeslot.timezone', 'parcel_job.pickup_instructions',
];

// ---- helpers ----
function csvEscape(v) {
  const s = String(v ?? '');
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
function writeCsv(file, header, rows) {
  const lines = [header.map(csvEscape).join(',')];
  for (const r of rows) lines.push(header.map(h => csvEscape(r[h] ?? '')).join(','));
  fs.writeFileSync(file, '﻿' + lines.join('\r\n'), 'utf8'); // BOM for Excel
}
function newToken() { return crypto.randomUUID().replace(/-/g, ''); }
function buildLink(rdoText, url) {
  return `<updated_addr>${rdoText} <a href="${url}">${url}</a></updated_addr>`;
}
// Fit free text + fixed suffix + link into the char limit, truncating the free text if needed.
// No separator inserted before the anchor — rdo_text entries carry their own trailing
// punctuation/spacing (mirrors backend/oc_engine.py's _fit_instr, 09 Jul 2026).
function fitInstr(freeText, suffix, url, limit) {
  const build = (t) => `<updated_addr>${[t, suffix].filter(Boolean).join('')}<a href="${url}">${url}</a></updated_addr>`;
  if (build(freeText).length <= limit) return { instr: build(freeText), truncated: false };
  // Iteratively trim the free text (with an ellipsis) until the whole field fits.
  let t = freeText;
  while (t.length > 0 && build(t.slice(0, t.length - 1) + '…').length > limit) t = t.slice(0, t.length - 1);
  const trimmed = t.length > 0 ? t.slice(0, t.length - 1) + '…' : '';
  return { instr: build(trimmed), truncated: true };
}

// ---- read source ----
const sheet = readSheet(args.in, 0);
const errors = [];
const links = [];      // { swipe_awb / return_awb, token, url }
const uploadRows = [];

if (svc.direction === 'forward') buildForward();
else buildReturn();

// ================= FORWARD (S1 / S2) =================
function buildForward() {
  const layout = config.source_layouts[svc.layout];
  const C = layout.cols;
  const cap = config.max_collies_per_awb;
  // Group by SwipeAWB. The AWB header (name/address/etc.) sits on the FIRST row of
  // the group; continuation rows carry only per-PO/per-collie data with a blank key.
  const order = [];
  const groups = new Map(); // SwipeAWB -> { firstRow, poLines:[{po,koli}], collies }
  let current = null;
  for (let r = layout.data_start_row; r <= sheet.maxR; r++) {
    const key = sheet.get(C.swipe_awb, r).trim();
    const po = sheet.get(C.po, r).trim();
    const hasData = key || po || sheet.get(C.name, r).trim() || (C.koli && sheet.get(C.koli, r).trim());
    if (!hasData) continue;
    if (key) {
      current = key;
      if (!groups.has(key)) { groups.set(key, { firstRow: r, poLines: [], collies: 0 }); order.push(key); }
    }
    if (!current) { errors.push({ row: r, awb: '', errors: 'orphan row before any SwipeAWB' }); continue; }
    const g = groups.get(current);
    if (layout.koli_mode === 'count') {
      const koliRaw = normNum(sheet.get(C.koli, r));
      const koli = parseInt(koliRaw, 10);
      if (!po) { errors.push({ row: r, awb: current, errors: 'missing PO Number' }); continue; }
      if (!(koli > 0)) { errors.push({ row: r, awb: current, errors: `koli must be > 0 (got "${koliRaw}")` }); continue; }
      g.poLines.push({ po, koli });
      g.collies += koli;
    } else { // one_row_per_collie: each data row is a single parcel
      if (po) g.poLines.push({ po, koli: null });
      g.collies += 1;
    }
  }

  for (const swipeAwb of order) {
    const g = groups.get(swipeAwb);
    const fr = g.firstRow;
    const total = g.collies;
    if (!(total > 0)) { errors.push({ row: fr, awb: swipeAwb, errors: 'no valid collies' }); continue; }
    if (total > cap) { errors.push({ row: fr, awb: swipeAwb, errors: `collie count ${total} exceeds cap ${cap} — likely a source-layout mismatch; skipped` }); continue; }
    const trids = total === 1 ? [swipeAwb] : Array.from({ length: total }, (_, i) => `${swipeAwb}-${i + 1}`);
    const token = newToken();
    const url = `https://${baseUrl}/c/${token}`;
    links.push({ scope: swipeAwb, token, url });

    const { instr } = fitInstr(config.rdo_text.forward, '', url, config.link_char_limit);
    const yDesc = layout.koli_mode === 'count'
      ? g.poLines.map(x => `${x.po} (${x.koli})`).join(', ') + ` — ${total} koli`
      : g.poLines.map(x => x.po).join(', ') + ` — ${total} koli`;

    for (const trid of trids) {
      uploadRows.push({
        'requested_tracking_number': trid,
        'global_shipper_id': config.master_shipper_id,
        'service_type': config.fixed.service_type,
        'reference.merchant_order_number': swipeAwb,
        'service_level': svc.service_level,
        'from.name': config.warehouse.name,
        'from.phone_number': config.warehouse.phone,
        'from.address.address1': config.warehouse.address1,
        'from.address.country': config.warehouse.country,
        'to.name': sheet.get(C.name, fr).trim(),
        'to.phone_number': normNum(sheet.get(C.phone, fr)),
        'to.address.address1': sheet.get(C.address, fr).trim(),
        'to.address.country': 'ID',
        'to.address.kecamatan': '', // NV auto-fills from postcode+city
        'to.address.city': sheet.get(C.city, fr).trim(),
        'to.address.province': '', // NV auto-fills
        'to.address.postcode': normNum(sheet.get(C.zip, fr)),
        'parcel_job.delivery_instructions': instr,
        'parcel_job.delivery_start_date': today,
        'parcel_job.delivery_timeslot.start_time': config.fixed.timeslot.start_time,
        'parcel_job.delivery_timeslot.end_time': config.fixed.timeslot.end_time,
        'parcel_job.delivery_timeslot.timezone': config.fixed.timeslot.timezone,
        'parcel_job.dimensions.weight': normNum(sheet.get(C.weight, fr)), // TMP weight (not the hardcoded-1 bug)
        'parcel_job.is_pickup_required': config.fixed.is_pickup_required_forward,
        'parcel_job.items.0.item_description': yDesc,
        'parcel_job.items.0.is_dangerous_good': config.fixed.is_dangerous_good,
        'b2b.documents_required': config.fixed.documents_required,
        'bundle_information.total_quantity': String(total),
        'bundle_information.requested_piece_tracking_numbers': trids.join(', '),
        'parcel_job.insured_value': config.fixed.insured_value,
        'corporate.branch_id': svc.branch_id,
      });
    }
  }
}

// ================= RETURN PICKUP (S3) =================
function buildReturn() {
  const layout = config.source_layouts[svc.layout];
  const C = layout.cols;
  for (let r = layout.data_start_row; r <= sheet.maxR; r++) {
    const returnAwb = sheet.get(C.return_awb, r).trim(); // airway bill return (AWBR-...)
    const po = sheet.get(C.po, r).trim();
    if (!returnAwb && !po) continue;
    const rowErr = [];
    if (!returnAwb) rowErr.push('missing return AWB');
    if (!sheet.get(C.address, r).trim()) rowErr.push('missing pharmacy address');
    if (rowErr.length) { errors.push({ row: r, awb: returnAwb, errors: rowErr.join('; ') }); continue; }

    // Return AWB is a single parcel here (samples: "-01"); MPS base = returnAwb.
    const trids = [`${returnAwb}-01`];
    const token = newToken();
    const url = `https://${baseUrl}/c/${token}`;
    const inv = sheet.get(C.inv, r).trim();
    const detail = sheet.get(C.detail, r).replace(/\s+/g, ' ').trim();
    // The full item detail + invoice live in the courier app (behind the link), not in R.
    links.push({ scope: returnAwb, token, url, invoice: inv, item_detail: detail });

    // R = short fixed instruction that MUST send the courier to the link (which holds the
    // variable-length item list + invoice). This keeps R well under 500 with no truncation.
    const { instr } = fitInstr(config.rdo_text.return_delivery_short, '', url, config.link_char_limit);

    uploadRows.push({
      'requested_tracking_number': trids[0],
      'global_shipper_id': config.master_shipper_id,
      'service_type': config.fixed.service_type,
      'reference.merchant_order_number': po, // return: merchant ref = PO Number
      'service_level': svc.service_level,
      'from.name': sheet.get(C.pharmacy_name, r).trim(), // pharmacy (pickup)
      'from.phone_number': normNum(sheet.get(C.phone, r)),
      'from.address.address1': sheet.get(C.address, r).trim(),
      'from.address.country': 'ID',
      'to.name': config.warehouse.name,                // SwipeRx WH (destination)
      'to.phone_number': config.warehouse.phone,
      'to.address.address1': config.warehouse.address1,
      'to.address.country': config.warehouse.country,
      'to.address.kecamatan': config.warehouse.kecamatan,
      'to.address.city': config.warehouse.city,
      'to.address.province': config.warehouse.province,
      'to.address.postcode': config.warehouse.postcode,
      'parcel_job.delivery_instructions': instr,
      'parcel_job.delivery_start_date': today,
      'parcel_job.delivery_timeslot.start_time': config.fixed.timeslot.start_time,
      'parcel_job.delivery_timeslot.end_time': config.fixed.timeslot.end_time,
      'parcel_job.delivery_timeslot.timezone': config.fixed.timeslot.timezone,
      'parcel_job.dimensions.weight': '1', // return: shipper default 1 kg (TMP E is '-')
      'parcel_job.is_pickup_required': config.fixed.is_pickup_required_return,
      'parcel_job.items.0.item_description': config.fixed.item_description_return,
      'parcel_job.items.0.is_dangerous_good': config.fixed.is_dangerous_good,
      'b2b.documents_required': config.fixed.documents_required,
      'bundle_information.total_quantity': '1',
      'bundle_information.requested_piece_tracking_numbers': trids.join(', '),
      'parcel_job.insured_value': config.fixed.insured_value,
      'corporate.branch_id': svc.branch_id,
      'parcel_job.pickup_date': today,
      'parcel_job.pickup_timeslot.start_time': config.fixed.timeslot.start_time,
      'parcel_job.pickup_timeslot.end_time': config.fixed.timeslot.end_time,
      'parcel_job.pickup_timeslot.timezone': config.fixed.timeslot.timezone,
      'parcel_job.pickup_instructions': config.rdo_text.return_pickup_instructions,
      '_inv': inv, // carried for the summary / Validator cross-check (not an upload column)
    });
  }
}

// ---- write outputs ----
const uploadCols = svc.direction === 'return' ? [...FWD_COLS, ...RET_EXTRA_COLS] : FWD_COLS;
writeCsv(path.join(outDir, 'upload.csv'), uploadCols, uploadRows);
// links.csv doubles as the courier-app payload: for returns it carries the full item detail + invoice
// that R deliberately omits (the courier opens the link to see them).
writeCsv(path.join(outDir, 'links.csv'), ['scope', 'token', 'url', 'invoice', 'item_detail'], links);

const maxInstrLen = uploadRows.reduce((m, r) => Math.max(m, (r['parcel_job.delivery_instructions'] || '').length), 0);
const realErrors = errors.filter(e => !e.warning);
const warnings = errors.filter(e => e.warning);
const summary = {
  input: path.basename(args.in),
  service, service_name: svc.name, movement: svc.movement, layout: svc.layout,
  branch_id: svc.branch_id, service_level: svc.service_level,
  base_url: baseUrl, date: today,
  awb_count: links.length,
  upload_row_count: uploadRows.length,
  error_count: realErrors.length,
  warning_count: warnings.length,
  max_delivery_instructions_len: maxInstrLen,
  char_limit: config.link_char_limit,
  errors: realErrors,
  warnings,
};
fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2), 'utf8');

console.log(`OC engine — ${service} (${svc.name}), movement ${svc.movement} [layout: ${svc.layout}]`);
console.log(`  input:        ${path.basename(args.in)}`);
console.log(`  AWBs:         ${links.length}`);
console.log(`  upload rows:  ${uploadRows.length} (TRID/MPS pieces)`);
console.log(`  branch_id:    ${svc.branch_id}   service_level: ${svc.service_level}`);
console.log(`  max R length: ${maxInstrLen} / ${config.link_char_limit}${maxInstrLen > config.link_char_limit ? '  ⚠ OVER LIMIT' : ''}`);
console.log(`  row errors:   ${realErrors.length}   warnings: ${warnings.length}`);
for (const e of realErrors.slice(0, 10)) console.log(`    - row ${e.row} [${e.awb}]: ${e.errors}`);
if (realErrors.length > 10) console.log(`    … +${realErrors.length - 10} more`);
console.log(`  wrote:        ${path.relative(process.cwd(), outDir)}/{upload.csv, links.csv, summary.json}`);
