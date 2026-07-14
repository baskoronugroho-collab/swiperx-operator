// Minimal XLSX reader: no deps. Unzip via built-in zlib on the raw zip entries.
const fs = require('fs');
const zlib = require('zlib');

function readZip(buf) {
  // Parse End Of Central Directory
  const entries = {};
  // find EOCD
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('no EOCD');
  let cdOff = buf.readUInt32LE(eocd + 16);
  let cdCount = buf.readUInt16LE(eocd + 10);
  let p = cdOff;
  for (let n = 0; n < cdCount; n++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) break;
    const method = buf.readUInt16LE(p + 10);
    const compSize = buf.readUInt32LE(p + 20);
    const nameLen = buf.readUInt16LE(p + 28);
    const extraLen = buf.readUInt16LE(p + 30);
    const commentLen = buf.readUInt16LE(p + 32);
    const localOff = buf.readUInt32LE(p + 42);
    const name = buf.slice(p + 46, p + 46 + nameLen).toString('utf8');
    // local header to find data start
    const lhNameLen = buf.readUInt16LE(localOff + 26);
    const lhExtraLen = buf.readUInt16LE(localOff + 28);
    const dataStart = localOff + 30 + lhNameLen + lhExtraLen;
    const comp = buf.slice(dataStart, dataStart + compSize);
    let data;
    if (method === 0) data = comp;
    else if (method === 8) data = zlib.inflateRawSync(comp);
    else throw new Error('unsupported method ' + method);
    entries[name] = data.toString('utf8');
    p += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

function colToNum(col) {
  let n = 0;
  for (const ch of col) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n;
}
function refToRC(ref) {
  const m = ref.match(/^([A-Z]+)(\d+)$/);
  return { c: colToNum(m[1]), r: parseInt(m[2], 10), col: m[1] };
}

function parseSharedStrings(xml) {
  if (!xml) return [];
  const out = [];
  const siRe = /<si>([\s\S]*?)<\/si>/g;
  let m;
  while ((m = siRe.exec(xml))) {
    const inner = m[1];
    const tRe = /<t[^>]*>([\s\S]*?)<\/t>/g;
    let t, s = '';
    while ((t = tRe.exec(inner))) s += t[1];
    out.push(decode(s));
  }
  return out;
}
function decode(s) {
  return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');
}

function parseSheet(xml, shared) {
  const cells = {};
  let maxR = 0, maxC = 0;
  const rowRe = /<row[^>]*r="(\d+)"[^>]*>([\s\S]*?)<\/row>/g;
  let rm;
  while ((rm = rowRe.exec(xml))) {
    const inner = rm[2];
    // Self-closing (empty) cell alternative MUST come first: otherwise the open-tag pattern's
    // [^>]* swallows a self-closing "<c .../>" plus the next valued cell, stealing its value.
    const cRe = /<c[^>]*r="([A-Z]+\d+)"([^>]*)\/>|<c[^>]*r="([A-Z]+\d+)"([^>]*)>([\s\S]*?)<\/c>/g;
    let cm;
    while ((cm = cRe.exec(inner))) {
      const ref = cm[1] || cm[3];
      const attrs = (cm[2] || cm[4] || '');
      const body = cm[5] || '';
      const { r, c, col } = refToRC(ref);
      maxR = Math.max(maxR, r); maxC = Math.max(maxC, c);
      const tMatch = attrs.match(/t="([^"]+)"/);
      const type = tMatch ? tMatch[1] : 'n';
      const fMatch = body.match(/<f[^>]*>([\s\S]*?)<\/f>/);
      const vMatch = body.match(/<v[^>]*>([\s\S]*?)<\/v>/);
      const isMatch = body.match(/<is>[\s\S]*?<t[^>]*>([\s\S]*?)<\/t>[\s\S]*?<\/is>/);
      let val = '';
      if (type === 's' && vMatch) val = shared[parseInt(vMatch[1], 10)] ?? '';
      else if (type === 'inlineStr' && isMatch) val = decode(isMatch[1]);
      else if (vMatch) val = decode(vMatch[1]);
      const formula = fMatch ? decode(fMatch[1]) : null;
      cells[ref] = { r, c, col, val, formula, type };
    }
  }
  return { cells, maxR, maxC };
}

function grid(sheet, limitRows) {
  const { cells, maxR, maxC } = sheet;
  const lines = [];
  const rows = Math.min(maxR, limitRows || maxR);
  for (let r = 1; r <= rows; r++) {
    const parts = [];
    for (let c = 1; c <= maxC; c++) {
      const col = numToCol(c);
      const cell = cells[col + r];
      let s = cell ? (cell.formula ? '=' + cell.formula : cell.val) : '';
      s = String(s).replace(/\s+/g, ' ').trim();
      if (s.length > 40) s = s.slice(0, 40) + '…';
      parts.push(s);
    }
    // trim trailing empties
    while (parts.length && parts[parts.length - 1] === '') parts.pop();
    if (parts.length) lines.push('R' + r + ' | ' + parts.map((p, i) => numToCol(i + 1) + ':' + p).join(' | '));
  }
  return lines.join('\n');
}
function numToCol(n) {
  let s = '';
  while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

function workbookSheets(entries) {
  const wb = entries['xl/workbook.xml'] || '';
  const rels = entries['xl/_rels/workbook.xml.rels'] || '';
  const sheets = [];
  const re = /<sheet[^>]*name="([^"]*)"[^>]*r:id="([^"]*)"[^>]*\/>|<sheet[^>]*name="([^"]*)"[^>]*sheetId="[^"]*"[^>]*r:id="([^"]*)"/g;
  let m;
  const nameRe = /<sheet [^>]*name="([^"]*)"[^>]*r:id="(rId\d+)"/g;
  while ((m = nameRe.exec(wb))) sheets.push({ name: decode(m[1]), rid: m[2] });
  // map rid -> target
  const relMap = {};
  const relRe = /<Relationship[^>]*Id="(rId\d+)"[^>]*Target="([^"]*)"/g;
  let rm;
  while ((rm = relRe.exec(rels))) relMap[rm[1]] = rm[2];
  return sheets.map(s => ({ name: s.name, target: 'xl/' + (relMap[s.rid] || '').replace(/^\/?/, '') }));
}

function dataValidations(xml) {
  const out = [];
  const re = /<dataValidation[^>]*sqref="([^"]*)"[^>]*>[\s\S]*?<formula1>([\s\S]*?)<\/formula1>|<dataValidation([^>]*)\/>/g;
  const dvRe = /<dataValidation\b([^>]*)>([\s\S]*?)<\/dataValidation>/g;
  let m;
  while ((m = dvRe.exec(xml))) {
    const attrs = m[1]; const body = m[2];
    const sq = (attrs.match(/sqref="([^"]*)"/) || [])[1] || '';
    const type = (attrs.match(/type="([^"]*)"/) || [])[1] || '';
    const f1 = (body.match(/<formula1>([\s\S]*?)<\/formula1>/) || [])[1] || '';
    out.push({ sqref: sq, type, formula1: decode(f1) });
  }
  return out;
}

// ---- main ----
const path = process.argv[2];
const sheetFilter = process.argv[3];
const buf = fs.readFileSync(path);
const entries = readZip(buf);
const shared = parseSharedStrings(entries['xl/sharedStrings.xml']);
const sheets = workbookSheets(entries);
console.log('=== FILE: ' + path.split(/[\\/]/).pop() + ' ===');
console.log('SHEETS: ' + sheets.map(s => s.name).join(' | '));
for (const s of sheets) {
  if (sheetFilter && !s.name.toLowerCase().includes(sheetFilter.toLowerCase())) continue;
  const xml = entries[s.target];
  if (!xml) { console.log('\n--- ' + s.name + ' (no xml at ' + s.target + ') ---'); continue; }
  const parsed = parseSheet(xml, shared);
  console.log('\n--- SHEET: ' + s.name + ' (rows=' + parsed.maxR + ', cols=' + numToCol(parsed.maxC) + ') ---');
  console.log(grid(parsed, 30));
  const dv = dataValidations(xml);
  if (dv.length) {
    console.log('  DATA VALIDATIONS (dropdowns/locked-choice):');
    for (const d of dv) console.log('   [' + d.sqref + '] type=' + d.type + ' → ' + d.formula1);
  }
}
