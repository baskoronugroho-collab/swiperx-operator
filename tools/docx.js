const fs = require('fs');
const zlib = require('zlib');
function readZip(buf){const e={};let eo=-1;for(let i=buf.length-22;i>=0;i--){if(buf.readUInt32LE(i)===0x06054b50){eo=i;break;}}let off=buf.readUInt32LE(eo+16),cnt=buf.readUInt16LE(eo+10),p=off;for(let n=0;n<cnt;n++){if(buf.readUInt32LE(p)!==0x02014b50)break;const method=buf.readUInt16LE(p+10),cs=buf.readUInt32LE(p+20),nl=buf.readUInt16LE(p+28),el=buf.readUInt16LE(p+30),cl=buf.readUInt16LE(p+32),lo=buf.readUInt32LE(p+42);const name=buf.slice(p+46,p+46+nl).toString('utf8');const lnl=buf.readUInt16LE(lo+26),lel=buf.readUInt16LE(lo+28),ds=lo+30+lnl+lel;const comp=buf.slice(ds,ds+cs);e[name]=method===0?comp:zlib.inflateRawSync(comp);p+=46+nl+el+cl;}return e;}
function dec(s){return s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&amp;/g,'&');}
const buf=fs.readFileSync(process.argv[2]);
const e=readZip(buf);
const xml=(e['word/document.xml']||Buffer.from('')).toString('utf8');
// Split into paragraphs, extract text runs, mark list/heading roughly.
const paras=xml.split(/<w:p[ >]/).slice(1);
const out=[];
for(const p of paras){
  const texts=[...p.matchAll(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g)].map(m=>dec(m[1]));
  let line=texts.join('');
  // tabs
  const tabs=(p.match(/<w:tab\/>/g)||[]).length;
  const isHeading=/w:val="(Heading|Title)/.test(p)||/pStyle[^>]*Heading/.test(p);
  line=line.replace(/\s+/g,' ').trim();
  if(line) out.push((isHeading?'## ':'')+line);
}
// tables
const tblCount=(xml.match(/<w:tbl>/g)||[]).length;
console.log('PARAGRAPHS: '+out.length+' | TABLES: '+tblCount);
console.log(out.join('\n'));
