import fs from 'fs';
const en = JSON.parse(fs.readFileSync('messages/en.json','utf8'));
const ru = JSON.parse(fs.readFileSync('messages/ru.json','utf8'));
function keys(o, p=''){ return Object.entries(o).flatMap(([k,v])=> v && typeof v==='object' && !Array.isArray(v) ? keys(v,p+k+'.') : [p+k]); }
const ek = new Set(keys(en)), rk = new Set(keys(ru));
const missingInRu = [...ek].filter(k=>!rk.has(k)), extraInRu = [...rk].filter(k=>!ek.has(k));
if(missingInRu.length||extraInRu.length){ console.error({missingInRu, extraInRu}); process.exit(1); }
console.log('i18n keys ok:', ek.size);
