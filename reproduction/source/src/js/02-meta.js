/* ==========================================================================
   Метаданные показателей: подпись, единица, вид значения, направление,
   форматирование. Один источник для всех вкладок (индекс m ≠ процентиль mp).
   ========================================================================== */

/* исходные значения индексов nodes[i].m: единицы следуют формулам D.metrics */
const IX_RAW = {
  localization:   {kind: 'share', unit: 'доля стоимости контрактов'},
  external_dep:   {kind: 'share', unit: 'доля контрактов'},
  competition:    {kind: 'share', unit: '1 − доля единственного поставщика'},
  budget_dep:     {kind: 'meanpct', unit: 'средний процентиль двух признаков'},
  online_leakage: {kind: 'share', unit: 'маркетплейсы / (маркетплейсы + общепит)'},
  activity:       {kind: 'meanpct', unit: 'средний процентиль трёх признаков'},
  demo_resilience:{kind: 'meanpct', unit: 'средний процентиль трёх признаков'},
  hub:            {kind: 'score', unit: 'PageRank, безразмерный', d: 3},
  supply_reach:   {kind: 'share', unit: 'доля МО региона'},
  bridge:         {kind: 'score', unit: 'betweenness, безразмерный', d: 4},
  sync:           {kind: 'score', unit: 'взвешенная степень', d: 2},
  leadership:     {kind: 'count', unit: 'число МО'},
  typicality:     {kind: 'score', unit: 'силуэт, −1…1', d: 2},
};
/* значение индекса в его собственных единицах */
function fmtIxRaw(k, v){
  if (v == null || Number.isNaN(v)) return 'н/д';
  const m = IX_RAW[k] || {kind: 'score', d: 2};
  if (m.kind === 'share') return fmtN(v * 100, 1) + '%';
  if (m.kind === 'meanpct') return fmtN(v, 1);
  if (m.kind === 'count') return fmtN(v, 0);
  return fmtN(v, m.d ?? 2);
}
/* процентиль среди МО — место на шкале 0–100, не процент */
const fmtPctile = v => v == null ? 'н/д' : fmtN(v, 0) + '-й процентиль';
const fmtPctileShort = v => v == null ? 'н/д' : fmtN(v, 0);
const ixLabel = k => D.metrics[k].label;
const ixSense = k => D.metrics[k].sense;
const senseWord = s => s > 0 ? 'выше — благоприятнее' : s < 0 ? 'выше — неблагоприятнее' : 'нейтральный, без оценки';

/* признаки D.feats: [подпись, единица] */
function featUnitText(k){ const u = (D.feats[k] || ['', ''])[1]; return u === '%' ? '%' : u === '' ? (k.startsWith('log_') ? 'лог. шкала' : 'безразмерный') : u; }
/* для осей: подпись + единица */
function axisName(v){ if (v.startsWith('m_')) { const k = v.slice(2), m = IX_RAW[k]; return D.metrics[k].label + (m && m.kind === 'share' ? ', %' : ''); }
  const u = (D.feats[v] || ['', ''])[1]; return featLabel(v) + (u === '%' ? ', %' : u ? ', ' + u : ''); }
/* значение переменной корреляции/графика (признак или исходный индекс) в единицах */
function fmtVar(v, x){ if (x == null) return 'н/д'; return v.startsWith('m_') ? fmtIxRaw(v.slice(2), x) : fmtF(v, x); }
/* число для оси: доли показываются в процентах */
function axisVal(v, x){ const share = v.startsWith('m_') ? (IX_RAW[v.slice(2)] || {}).kind === 'share' : (D.feats[v] || [])[1] === '%'; return share ? x * 100 : x; }
function isShareVar(v){ return v.startsWith('m_') ? (IX_RAW[v.slice(2)] || {}).kind === 'share' : (D.feats[v] || [])[1] === '%'; }

/* типы: стабильный порядок из D.types, цвет по названию (как в исходной сборке) */
const TYPES = D.types.map(t => ({c: t.c, name: t.name, members: t.members.slice()}));
const typeOf = i => N[i].c;
