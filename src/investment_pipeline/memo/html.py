"""Render an AnalyzedCandidate into a styled, self-contained HTML memo.

Same content as the markdown memo (render.py), but laid out as an editorial
one-pager a partner would enjoy skimming: a colour-coded call, a score dial with
a per-rule breakdown, clean sections, and a sources list. Fully self-contained
(inline CSS, no external assets) so the file opens straight from disk.
"""

from html import escape

from ..analysis.analyze import slug
from ..models import AnalyzedCandidate

# Accent colour + label per recommendation call.
_CALL = {
    "Take a meeting": ("#0f9d58", "🟢"),
    "Watch": ("#f2a600", "🟡"),
    "Pass": ("#db4437", "🔴"),
}

_CSS = """
:root { --ink:#1a1a1a; --muted:#6b6b6b; --line:#e7e4dd; --bg:#f6f4ee;
        --card:#ffffff; --accent:#0f9d58; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:820px; margin:0 auto; padding:32px 20px 64px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px;
        overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.04); }
.accent-bar { height:6px; background:var(--accent); }
.pad { padding:32px 40px; }
.badge { display:inline-block; padding:5px 14px; border-radius:999px;
         background:var(--accent); color:#fff; font-weight:700; font-size:13px;
         letter-spacing:.04em; text-transform:uppercase; }
h1 { font-family:Georgia,"Times New Roman",serif; font-size:34px; line-height:1.15;
     margin:14px 0 6px; }
.oneliner { font-size:18px; color:var(--muted); margin:0 0 16px; }
.meta { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 4px; }
.tag { font-size:12.5px; color:var(--muted); background:#f0eee7; border:1px solid var(--line);
       border-radius:6px; padding:3px 9px; }
.tag a { color:var(--accent); text-decoration:none; }
.scorebox { display:flex; gap:24px; align-items:center; margin:28px 0 8px;
            padding:20px; background:#faf9f5; border:1px solid var(--line); border-radius:12px; }
.dial { flex:0 0 96px; width:96px; height:96px; border-radius:50%;
        display:grid; place-items:center; color:#fff;
        background:conic-gradient(var(--accent) calc(var(--pct)*1%), #e3e0d8 0); }
.dial .inner { width:74px; height:74px; border-radius:50%; background:var(--card);
               display:grid; place-items:center; color:var(--ink); }
.dial b { font-size:26px; } .dial span { font-size:11px; color:var(--muted); }
.bars { flex:1 1 auto; min-width:0; }
.bar { margin:0 0 10px; }
.bar-top { display:flex; justify-content:space-between; font-size:13px; }
.bar-top .num { color:var(--muted); font-variant-numeric:tabular-nums; }
.track { height:7px; background:#e6e3db; border-radius:4px; margin:3px 0 2px; overflow:hidden; }
.fill { height:100%; background:var(--accent); border-radius:4px; }
.bar-reason { font-size:12px; color:var(--muted); }
h2 { font-family:Georgia,serif; font-size:16px; text-transform:uppercase; letter-spacing:.06em;
     color:var(--muted); border-bottom:1px solid var(--line); padding-bottom:6px;
     margin:34px 0 12px; }
p { margin:0 0 12px; }
.callout { background:#faf9f5; border-left:4px solid var(--accent); border-radius:0 8px 8px 0;
           padding:14px 18px; margin:6px 0 8px; }
ul.clean { list-style:none; padding:0; margin:0; }
ul.clean li { padding:9px 0 9px 26px; position:relative; border-bottom:1px solid var(--line); }
ul.clean li:last-child { border-bottom:none; }
ul.risks li::before { content:"⚠"; position:absolute; left:0; color:#c58a00; }
ul.change li::before { content:"→"; position:absolute; left:0; color:var(--accent); font-weight:700; }
.sources { font-size:13.5px; }
.sources li { padding:8px 0; border-bottom:1px dashed var(--line); }
.chip { display:inline-block; font-size:11px; font-weight:600; background:#eef4f0;
        color:#256; border-radius:5px; padding:2px 7px; margin-right:8px; }
.sources a { color:var(--accent); }
.foot { margin-top:26px; padding-top:16px; border-top:1px solid var(--line);
        font-size:12px; color:var(--muted); }
.back { display:inline-block; margin-bottom:16px; font-size:13px; color:var(--muted); text-decoration:none; }
@media (max-width:560px){ .pad{padding:24px 20px;} .scorebox{flex-direction:column;align-items:stretch;} }
"""


def _paras(text: str) -> str:
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        blocks = [text.strip()]
    return "".join(f"<p>{escape(b).replace(chr(10), ' ')}</p>" for b in blocks)


def _bars(components) -> str:
    rows = []
    for c in components:
        pct = (c.points / c.max_points * 100) if c.max_points else 0
        rows.append(
            f'<div class="bar"><div class="bar-top"><span>{escape(c.name)}</span>'
            f'<span class="num">{c.points:.0f}/{c.max_points:.0f}</span></div>'
            f'<div class="track"><div class="fill" style="width:{pct:.0f}%"></div></div>'
            f'<div class="bar-reason">{escape(c.reason)}</div></div>'
        )
    return "".join(rows)


def _sources(citations) -> str:
    items = []
    for cit in citations:
        link = f' <a href="{escape(str(cit.url))}">link</a>' if cit.url else ""
        items.append(
            f'<li><span class="chip">{escape(cit.source)}</span>'
            f'{escape(cit.claim)}{link}</li>'
        )
    return "".join(items)


def render_html(ac: AnalyzedCandidate) -> str:
    c, a = ac.candidate, ac.analysis
    accent, mark = _CALL.get(ac.recommendation, ("#555", ""))

    tags = []
    if c.website:
        tags.append(f'<span class="tag"><a href="{escape(str(c.website))}">'
                    f'{escape(str(c.website))}</a></span>')
    if c.batch:
        tags.append(f'<span class="tag">YC {escape(c.batch)}</span>')
    if c.location:
        tags.append(f'<span class="tag">{escape(c.location)}</span>')
    if c.team_size is not None:
        tags.append(f'<span class="tag">team {c.team_size}</span>')

    risks = "".join(f"<li>{escape(r)}</li>" for r in a.risks)
    changes = "".join(f"<li>{escape(w)}</li>" for w in a.what_would_change_our_mind)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(c.name)} — {escape(ac.recommendation)}</title>
<style>{_CSS}</style></head>
<body style="--accent:{accent};">
<div class="wrap">
  <a class="back" href="index.html">← all memos</a>
  <article class="card">
    <div class="accent-bar"></div>
    <div class="pad">
      <span class="badge">{mark} {escape(ac.recommendation)}</span>
      <h1>{escape(c.name)}</h1>
      <p class="oneliner">{escape(c.description)}</p>
      <div class="meta">{''.join(tags)}</div>

      <div class="scorebox">
        <div class="dial" style="--pct:{ac.score.total};">
          <div class="inner"><div style="text-align:center">
            <b>{ac.score.total}</b><br><span>/100 · {escape(ac.score.band())}</span>
          </div></div>
        </div>
        <div class="bars">{_bars(ac.score.components)}</div>
      </div>

      <h2>Recommendation — {escape(ac.recommendation)}</h2>
      <div class="callout">{_paras(a.recommendation_rationale)}</div>

      <h2>Team</h2>{_paras(a.team)}
      <h2>Product</h2>{_paras(a.product)}
      <h2>Market</h2>{_paras(a.market)}

      <h2>Risks &amp; open questions</h2>
      <ul class="clean risks">{risks}</ul>

      <h2>What would change our mind</h2>
      <ul class="clean change">{changes}</ul>

      <h2>Sources</h2>
      <ul class="clean sources">{_sources(a.citations)}</ul>

      <div class="foot">Thesis: {escape(ac.score.thesis)}. Sourced from Y Combinator ·
        scored by rule-based thesis fit · analysis grounded in the sources above.<br>
        Discovery: <a href="{escape(str(c.discovery.source_url))}">{escape(str(c.discovery.source_url))}</a>
      </div>
    </div>
  </article>
</div>
</body></html>"""


def render_index_html(analyzed: list[AnalyzedCandidate]) -> str:
    ranked = sorted(analyzed, key=lambda a: a.score.total, reverse=True)
    thesis = escape(ranked[0].score.thesis) if ranked else ""

    rows = []
    for i, ac in enumerate(ranked, 1):
        accent, mark = _CALL.get(ac.recommendation, ("#555", ""))
        rows.append(
            f'<tr><td class="rk">{i}</td>'
            f'<td><a href="{slug(ac.candidate.name)}.html">{escape(ac.candidate.name)}</a>'
            f'<div class="ol">{escape(ac.candidate.description)}</div></td>'
            f'<td class="sc">{ac.score.total}</td>'
            f'<td><span class="pill" style="background:{accent}">{mark} '
            f'{escape(ac.recommendation)}</span></td></tr>'
        )

    css = """
    body{margin:0;background:#f6f4ee;color:#1a1a1a;
         font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;}
    .wrap{max-width:900px;margin:0 auto;padding:40px 20px;}
    h1{font-family:Georgia,serif;font-size:30px;margin:0 0 4px;}
    .sub{color:#6b6b6b;margin:0 0 24px;}
    table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e7e4dd;
          border-radius:12px;overflow:hidden;}
    th,td{padding:12px 16px;text-align:left;border-bottom:1px solid #efece5;vertical-align:top;}
    th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#6b6b6b;background:#faf9f5;}
    tr:last-child td{border-bottom:none;}
    .rk{color:#9a968c;width:34px;} .sc{font-weight:700;font-variant-numeric:tabular-nums;width:60px;}
    td a{color:#0f9d58;text-decoration:none;font-weight:600;}
    .ol{font-size:13px;color:#6b6b6b;font-weight:400;margin-top:2px;}
    .pill{color:#fff;border-radius:999px;padding:3px 11px;font-size:12.5px;font-weight:700;white-space:nowrap;}
    """
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Investment Pipeline — Memos</title><style>{css}</style></head>
<body><div class="wrap">
<h1>Investment Pipeline — Memos</h1>
<p class="sub">{len(ranked)} candidates ranked by rule-based thesis fit · <em>{thesis}</em></p>
<table><thead><tr><th>#</th><th>Company</th><th>Score</th><th>Call</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</div></body></html>"""
