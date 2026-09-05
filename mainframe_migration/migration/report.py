"""Write the single human-facing report: progress, validation, and SME questions.

The adjacent JSON files are machine evidence, not more documents for SMEs to read.
All content is escaped, the report loads no external scripts/fonts, and untested
platforms are shown explicitly rather than hidden behind a percentage complete.
"""
from __future__ import annotations
from html import escape
from pathlib import Path
from urllib.parse import quote
from .common import atomic_write

def write_report(folder: Path, result: dict) -> Path:
    """Publish one self-contained HTML report, including incomplete/blocked runs."""
    e=lambda value:escape(str(value))
    def table(headers,rows):
        return '<table><thead><tr>'+''.join('<th>'+e(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
    metrics=result.get('metrics',{})
    cards=[('Jobs generated',f'{metrics.get("jobs_generated",0)} / {metrics.get("jobs_discovered",0)}'),
           ('Cases passed',f'{metrics.get("cases_passed",0)} / {metrics.get("cases_planned",0)}'),
           ('Reusable jobs',str(metrics.get('cache_hits',0))),('Open questions',str(len(result.get('issues',[]))))]
    blocks=['<div class="cards">'+''.join('<div class="card"><span>'+e(label)+'</span><strong>'+e(value)+'</strong></div>' for label,value in cards)+'</div>']
    blocks+=['<h2>1. What this result means</h2><p>'+e(result.get('meaning','No application equivalence has been established.'))+'</p>',
      '<p class="notice">No source business rule was repaired. No Oracle, BigQuery, IBM z/OS, actual Copilot/Devin session, or Windows-laptop validation is implied by this run.</p>',
      '<p>Execution environment: '+e(result.get('environment','unknown'))+'<br>Baseline: '+e(result.get('baseline','not provided'))+'<br>Run folder: <code>'+e(folder)+'</code></p>']
    blocks+=['<h2>2. Job and source coverage</h2>',table(['Job','Generation route','Result','Source statements mapped','Artifact'],[(j['name'],j.get('mode','not generated'),j.get('status','blocked'),j.get('statement_count','not measured'),j.get('artifact','none')) for j in result.get('jobs',[])])]
    blocks+=['<p>Statement counts cover only the parsed/agent-mapped source. They are not a claim of full business-rule coverage. Unresolved dependencies remain blockers. Utility steps are counted as steps, not COBOL statements.</p>']
    blocks+=['<p>Discovered source members: '+e(metrics.get('source_members',0))+'. JCL steps: '+e(metrics.get('steps',0))+'. Observed translated statements: '+e(metrics.get('statements_observed',0))+' / '+e(metrics.get('statements_mapped',0))+'. Unvisited statements remain untested.</p>']
    blocks+=['<h2>3. Local execution and comparisons</h2>',table(['Scenario','Result','File checks','Database checks','Detail'],[(c['name'],c.get('status','not run'),c.get('file_passed',0).__str__()+' / '+str(c.get('file_total',0)),str(c.get('database_passed',0))+' / '+str(c.get('database_total',0)),c.get('detail','')) for c in result.get('cases',[])])]
    comparisons=[(c['name'],d.get('kind',''),d.get('name',''),d.get('status',''),d.get('detail','')) for c in result.get('cases',[]) for d in c.get('comparisons',[])]
    if comparisons:blocks+=['<details><summary>Open individual file and table comparison results</summary>',table(['Scenario','Kind','Object','Result','Evidence'],comparisons),'</details>']
    blocks+=['<h2>4. Questions and blockers — the one exception queue</h2>']
    issues=result.get('issues',[])
    blocks+=[table(['ID','Who can answer','Job / source','Question or required evidence'],[(q['id'],q.get('owner','Mainframe SME'),(q.get('job','')+' / '+q.get('source','')).strip(' /'),q['question']) for q in issues]) if issues else '<p>No blocking exceptions were found for the tested scope.</p>']
    blocks+=['<p>Record answers in <code>knowledge/answers.json</code> with the question ID, exact answer, scope, approver, and evidence. An answer is retained, but it cannot magically replace a missing executable member or table definition. Rerun the same command after supplying the evidence.</p>']
    blocks+=['<h2>5. Read-only review and integrity</h2>',table(['Check','Outcome'],[(x['check'],x['outcome']) for x in result.get('review',[])])]
    blocks+=['<h2>6. Saved knowledge and reuse</h2><p>Approved applicable answers: '+e(metrics.get('knowledge_answers',0))+'. Generation cache hits: '+e(metrics.get('cache_hits',0))+'. New offline generations: '+e(metrics.get('new_generations',0))+'. Test execution is repeated in a new database; prior pass/fail results are never reused. AI credit usage is not measured by this local runner.</p>']
    blocks+=['<h2>7. What is not complete</h2><ul>'+''.join('<li>'+e(s)+'</li>' for s in result.get('limitations',[]))+'</ul>']
    links=[]
    for p in sorted((folder/'code').glob('*.py')) if (folder/'code').exists() else []:
        rel=p.relative_to(folder).as_posix();links.append(f'<a href="{quote(rel)}">{e(p.name)}</a>')
    for rel in ('ddl/local.sql','ddl/logical_schema.json','discovery.json','result.json','agent_request.json'):
        if (folder/rel).exists():links.append(f'<a href="{quote(rel)}">{e(rel)}</a>')
    blocks+=['<h2>8. Artifacts and detailed evidence</h2><p>'+' &nbsp; | &nbsp; '.join(links)+'</p>',
      '<h2>9. What happened, in order</h2>',table(['Stage','Detail'],[(s['stage'],s['detail']) for s in result.get('stages',[])])]
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Migration report</title><style>
body{margin:0;background:#edf1f5;color:#182c40;font:16px/1.55 system-ui,Segoe UI,Arial,sans-serif}main{max-width:1160px;margin:28px auto;padding:36px;background:white;border-radius:12px}h1{font-size:32px;line-height:1.15;margin:8px 0 18px}h2{font-size:22px;margin-top:32px;border-top:1px solid #d8e0e8;padding-top:22px}.eyebrow{font-size:12px;letter-spacing:2px;font-weight:700;color:#506982}.status{display:inline-block;padding:7px 12px;background:#e7eef5;font-weight:700;border-radius:6px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:24px}.card{background:#f0f5fa;padding:16px;border-radius:8px}.card span{display:block;color:#516779}.card strong{display:block;font-size:30px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:11px;text-align:left;vertical-align:top;border-bottom:1px solid #dce4ec;overflow-wrap:anywhere}th{background:#e9f0f6}code{font:13px Consolas,monospace;overflow-wrap:anywhere}.notice{padding:14px;border-left:4px solid #ba7a21;background:#fff5e4}summary{cursor:pointer;font-weight:600;margin:12px 0}a{color:#156497}@media(max-width:700px){main{padding:18px;margin:8px}.cards{grid-template-columns:1fr 1fr}table{font-size:12px}}@media print{body{background:white}main{margin:0;padding:0}details{display:block}}
</style><main><div class="eyebrow">BEHAVIOR-PRESERVING MIGRATION / RUN EVIDENCE</div><h1>'''+e(result.get('process','Unknown process'))+'</h1><div class="status">'+e(result.get('status','INCOMPLETE'))+'</div>'+''.join(blocks)+'</main></html>'
    target=folder/'modernization_report.html';atomic_write(target,html);return target
