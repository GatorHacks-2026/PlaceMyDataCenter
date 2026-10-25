import type { AgentBattleResult } from './agenticBattle'
import type { SiteScreeningResult } from './siteScreening'

const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char] as string)

const verdictLabels: Record<AgentBattleResult['verdict_code'], string> = {
  INCOMPLETE: 'Incomplete screening',
  FAVOURABLE: 'Favourable screening',
  CONDITIONAL: 'Conditions required',
  NOT_AS_PLANNED: 'Not as planned',
}

function factRows(report: string): string {
  const section = report.match(/THE FACTS THEY USED\s*\n-+\s*\n([\s\S]*?)\n\s*THE CONVERSATION/)
  if (!section) return '<p class="muted">No screening facts were included in this report.</p>'
  return section[1].split('\n').map(line => line.trim()).filter(Boolean).map(line => {
    const match = line.match(/^([^[]+?)\s*\[([^\]]+)\]:\s*(.*)$/)
    if (!match) return `<div class="fact fact-note"><span>${escapeHtml(line)}</span></div>`
    const status = match[2].toLowerCase()
    const tone = status === 'red' ? 'red' : status === 'amber' ? 'amber' : status === 'green' ? 'green' : 'unknown'
    return `<div class="fact"><strong>${escapeHtml(match[1].trim())}</strong><span class="badge ${tone}">${escapeHtml(match[2])}</span><span>${escapeHtml(match[3])}</span></div>`
  }).join('')
}

export function buildAgentBattlePrintHtml(result: AgentBattleResult, screening: SiteScreeningResult): string {
  const verdict = verdictLabels[result.verdict_code] || 'Screening result'
  const capacityLabel = screening.input.capacity_basis === 'reported_it' ? 'Reported IT capacity' : 'Hypothetical IT capacity'
  const conversation = result.conversation.map((turn, index) => {
    const speaker = turn.speaker === 'sentinel' ? 'Sentinel' : 'Catalyst'
    return `<article class="turn ${turn.speaker}"><div class="turn-title"><span>${String(index + 1).padStart(2, '0')}</span><strong>${speaker}</strong><small>${turn.speaker === 'sentinel' ? 'Environmental critic' : 'Project advocate'}</small></div><p>${escapeHtml(turn.text)}</p></article>`
  }).join('')
  const unverified = result.unverified_numbers.length
    ? `<div class="notice warning"><strong>Numbers to verify</strong><p>The number check could not match these to the screening facts: ${escapeHtml(result.unverified_numbers.join(', '))}.</p></div>`
    : '<div class="notice"><strong>Number check</strong><p>The report found no numbers in the agents’ statements that were absent from its screening facts.</p></div>'
  const economics = result.report.match(/(?:Economic inputs you supplied:|Jobs \/ tax \/ investment numbers:)[^\n]*/)?.[0]

  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Agent Battle — ${escapeHtml(result.project_name)}</title><style>
    @page{size:letter;margin:15mm 14mm}
    *{box-sizing:border-box}body{margin:0;color:#172338;font:10pt/1.48 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;background:white}
    h1,h2,h3,p{margin:0}h1{font-size:24pt;line-height:1.15;letter-spacing:-.035em}h2{font-size:12pt;margin:0 0 10px;color:#102c3a}p{margin:0 0 8px}small,.muted{color:#64748b}
    .eyebrow{color:#087e76;font-size:8pt;font-weight:800;letter-spacing:.13em;text-transform:uppercase;margin-bottom:8px}
    .hero{border-top:7px solid #0d9488;padding:23px 0 20px;border-bottom:1px solid #dce6eb}.hero p{color:#526277;margin-top:9px;font-size:10pt}
    .meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:17px}.meta span{padding:5px 9px;border-radius:5px;background:#edf7f6;color:#075e59;font-size:8.4pt;font-weight:700}
    section{margin-top:25px}.section-heading{display:flex;align-items:center;gap:12px;border-bottom:2px solid #b9e6df;padding-bottom:7px;margin-bottom:12px}.section-heading h2{margin:0}.section-heading span{color:#0c8d83;font-size:8pt;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
    .verdict{padding:17px 19px;border-radius:8px;background:#f0f7f7;border-left:5px solid #0d9488;break-inside:avoid}.verdict strong{display:block;color:#075e59;font-size:13pt;margin-bottom:6px}.verdict p{color:#415365;margin:0}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:13px}.agent-card{border:1px solid #dce6eb;border-radius:8px;padding:14px;break-inside:avoid}.agent-card strong{display:block;font-size:10pt;margin-bottom:6px}.agent-card p{margin:0}.agent-card.sentinel{border-top:4px solid #d35c66}.agent-card.catalyst{border-top:4px solid #0d9488}
    .fact{display:grid;grid-template-columns:104px 75px 1fr;gap:10px;align-items:start;padding:9px 8px;border-bottom:1px solid #e2e8ef;break-inside:avoid}.fact:nth-child(odd){background:#f8fafb}.fact strong{font-size:9pt}.fact span:last-child{overflow-wrap:anywhere}.fact-note{display:block;color:#46576a;font-size:9pt}.badge{display:inline-block;width:max-content;padding:2px 6px;border-radius:4px;font-size:7.5pt;font-weight:800}.badge.red{background:#fde8ea;color:#a32d3c}.badge.amber{background:#fff0ce;color:#815308}.badge.green{background:#dcf7e9;color:#126b42}.badge.unknown{background:#e9edf2;color:#48596c}
    .turn{padding:13px 15px;margin-bottom:10px;border:1px solid #e0e7ed;border-left:4px solid #d35c66;border-radius:6px;break-inside:avoid}.turn.catalyst{border-left-color:#0d9488}.turn-title{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}.turn-title span{font-size:8pt;color:#8795a5;font-weight:800}.turn-title small{font-size:8pt}.turn p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
    .notice{padding:13px 15px;border:1px solid #b9e6df;border-radius:6px;background:#f4faf9;break-inside:avoid}.notice.warning{border-color:#f1cf8a;background:#fff9ed}.notice p{margin:4px 0 0}.source-note{margin-top:12px;color:#526277;font-size:9pt}.footer{margin-top:26px;border-top:1px solid #dce6eb;padding-top:9px;font-size:8pt;color:#64748b}
    @media screen{body{max-width:850px;margin:32px auto;padding:0 30px}.hero{margin-top:16px}}
    @media print{.turn,.agent-card,.verdict,.fact,.notice{page-break-inside:avoid}section{break-before:auto}.footer{break-inside:avoid}}
  </style></head><body>
    <header class="hero"><div class="eyebrow">Data Center Lens · Site review</div><h1>Sentinel vs Catalyst</h1><p>${escapeHtml(result.project_name)}${result.location_label ? ` · ${escapeHtml(result.location_label)}` : ''}</p><div class="meta"><span>${escapeHtml(verdict)}</span><span>${escapeHtml(screening.input.it_capacity_mw)} MW · ${capacityLabel}</span><span>${escapeHtml(screening.site.state)}</span><span>${escapeHtml(result.research_claims_used)} source-linked claims used</span></div><p class="site-detail">Placed site: ${escapeHtml(screening.site.lat.toFixed(4))}, ${escapeHtml(screening.site.lng.toFixed(4))} · Screening radius: ${escapeHtml(screening.input.radius_miles)} miles · Status: ${escapeHtml(screening.status)}</p></header>
    <section><div class="section-heading"><span>01</span><h2>At a glance</h2></div><div class="verdict"><strong>${escapeHtml(verdict)}</strong><p>Preliminary site screening. Local capacity, permits, and any unverified figures still require independent confirmation.</p></div><div class="two"><div class="agent-card sentinel"><strong>Sentinel · Environmental critic</strong><p>${escapeHtml(result.bottom_line.sentinel)}</p></div><div class="agent-card catalyst"><strong>Catalyst · Project advocate</strong><p>${escapeHtml(result.bottom_line.catalyst)}</p></div></div></section>
    <section><div class="section-heading"><span>02</span><h2>Screening facts used</h2></div>${factRows(result.report)}</section>
    <section><div class="section-heading"><span>03</span><h2>The conversation</h2></div>${conversation || '<p class="muted">No conversation was returned.</p>'}</section>
    <section><div class="section-heading"><span>04</span><h2>Evidence and limits</h2></div>${unverified}${economics ? `<p class="source-note">${escapeHtml(economics)}</p>` : ''}<p class="source-note">Agent statements are AI generated. Screening estimates and linked research claims come from the backend; this report is a reasoning aid, not a permitting decision or a measurement of actual impacts.</p></section>
    <footer class="footer">Data Center Lens · Generated ${escapeHtml(new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }))} · Review underlying sources and assumptions before sharing conclusions.</footer>
    <script>window.onload=()=>setTimeout(()=>window.print(),250)</script>
  </body></html>`
}
