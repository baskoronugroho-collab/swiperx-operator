// Minimal dependency-free XLSX reader (ESM). Reads the first (or named) worksheet
// into a cell map keyed by A1 reference. Adapted from tools/xlsx.js.
import fs from 'node:fs';
import zlib from 'node:zlib';

function readZip(buf) {
  const entries = {};
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('no EOCD (not a valid xlsx)');
  const cdOff = buf.readUInt32LE(eocd + 16);
  const cdCount = buf.readUInt16LE(eocd + 10);
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
    const lhNameLen = buf.readUInt16LE(localOff + 26);
    const lhExtraLen = buf.readUInt16LE(localOff + 28);
    const dataStart = localOff + 30 + lhNameLen + lhExtraLen;
    const comp = buf.slice(dataStart, dataStart + compSize);
    let data;
    if (method === 0) data = comp;
    else if (method === 8) data = zlib.inflateRawSync(comp);
    else throw new Error('unsupported zip method ' + method);
    entries[name] = data.toString('utf8');
    p += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

function decode(s) {
  return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');
}
export function colToNum(col) { let n = 0; for (const ch of col) n = n * 26 + (ch.charCodeAt(0) - 64); return n; }
export function numToCol(n) { let s = ''; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }
function refToRC(ref) { const m = ref.match(/^([A-Z]+)(\d+)$/); return { c: colToNum(m[1]), r: parseInt(m[2], 10), col: m[1] }; }

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
      const { r, c } = refToRC(ref);
      maxR = Math.max(maxR, r); maxC = Math.max(maxC, c);
      const tMatch = attrs.match(/t="([^"]+)"/);
      const type = tMatch ? tMatch[1] : 'n';
      const vMatch = body.match(/<v[^>]*>([\s\S]*?)<\/v>/);
      const isMatch = body.match(/<is>[\s\S]*?<t[^>]*>([\s\S]*?)<\/t>[\s\S]*?<\/is>/);
      let val = '';
      if (type === 's' && vMatch) val = shared[parseInt(vMatch[1], 10)] ?? '';
      else if (type === 'inlineStr' && isMatch) val = decode(isMatch[1]);
      else if (vMatch) val = decode(vMatch[1]);
      cells[ref] = String(val);
    }
  }
  return { cells, maxR, maxC };
}

function workbookSheets(entries) {
  const wb = entries['xl/workbook.xml'] || '';
  const rels = entries['xl/_rels/workbook.xml.rels'] || '';
  const sheets = [];
  const nameRe = /<sheet [^>]*name="([^"]*)"[^>]*r:id="(rId\d+)"/g;
  let m;
  while ((m = nameRe.exec(wb))) sheets.push({ name: decode(m[1]), rid: m[2] });
  const relMap = {};
  const relRe = /<Relationship[^>]*Id="(rId\d+)"[^>]*Target="([^"]*)"/g;
  let rm;
  while ((rm = relRe.exec(rels))) relMap[rm[1]] = rm[2];
  return sheets.map(s => ({ name: s.name, target: 'xl/' + (relMap[s.rid] || '').replace(/^\/?/, '') }));
}

/**
 * Read a worksheet. Returns { get(col,row), raw(ref), maxR, maxC, sheetName }.
 * @param {string} filePath
 * @param {number} [sheetIndex=0]
 */
export function readSheet(filePath, sheetIndex = 0) {
  const buf = fs.readFileSync(filePath);
  const entries = readZip(buf);
  const shared = parseSharedStrings(entries['xl/sharedStrings.xml']);
  const sheets = workbookSheets(entries);
  const s = sheets[sheetIndex];
  if (!s) throw new Error('no sheet at index ' + sheetIndex);
  const xml = entries[s.target];
  if (!xml) throw new Error('sheet xml missing: ' + s.target);
  const { cells, maxR, maxC } = parseSheet(xml, shared);
  return {
    sheetName: s.name,
    maxR, maxC,
    raw: (ref) => cells[ref] ?? '',
    get: (col, row) => cells[col + row] ?? '',
  };
}

/** Normalize numeric artefacts: scientific notation → full integer, strip trailing ".0". */
export function normNum(v) {
  const s = String(v ?? '').trim();
  if (s === '') return '';
  if (/^-?\d+(\.\d+)?[eE][+-]?\d+$/.test(s)) {
    const n = Number(s);
    if (Number.isInteger(n)) return n.toLocaleString('fullwide', { useGrouping: false });
    return String(n);
  }
  if (/^-?\d+\.0+$/.test(s)) return s.replace(/\.0+$/, '');
  return s;
}
