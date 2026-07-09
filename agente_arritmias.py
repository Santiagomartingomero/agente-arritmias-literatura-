"""
Agente de Revisión Bibliográfica en Arritmias
Autor: Santiago Martín Gomero
Fuente: Europe PMC API (gratuita, 45M+ papers biomédicos)

Genera automáticamente un blog clínico semanal en HTML para electrofisiólogos.
"""

import requests
from datetime import datetime, timedelta
import json
import os
import re

# =============================================================================
# CONFIGURACIÓN — Áreas de interés EP
# =============================================================================

KEYWORDS = {
    'Fibrilacion Auricular': [
        '"atrial fibrillation" AND ablation',
        '"atrial fibrillation" AND "pulmonary vein isolation"',
        '"atrial fibrillation" AND "left atrial appendage" closure',
        '"atrial fibrillation" AND anticoagulation AND bleeding',
        '"atrial fibrillation" AND "risk stratification" AND stroke',
        '"atrial fibrillation" AND "pulsed field ablation"',
        '"atrial fibrillation" AND cryoballoon',
    ],
    'Taquicardia Ventricular': [
        '"ventricular tachycardia" AND catheter ablation',
        '"ventricular tachycardia" AND "substrate modification"',
        '"ventricular fibrillation" AND prevention AND ICD',
        '"ischemic cardiomyopathy" AND "ventricular arrhythmias"',
        '"ventricular tachycardia" AND "stereotactic radiotherapy"',
        '"sudden cardiac death" AND prevention',
    ],
    'TSV y Vias Accesorias': [
        '"supraventricular tachycardia" AND ablation',
        '"AVNRT" OR "atrioventricular nodal reentrant tachycardia"',
        '"accessory pathway" AND ablation',
        '"Wolff-Parkinson-White" AND ablation',
        '"focal atrial tachycardia" AND ablation',
        '"atrial flutter" AND "cavotricuspid isthmus" AND ablation',
        '"atrioventricular reentrant tachycardia"',
    ],
    'Dispositivos Cardiacos': [
        '"leadless pacemaker" AND outcomes',
        '"cardiac resynchronization therapy" AND "non-responders"',
        '"subcutaneous ICD" AND outcomes',
        '"implantable loop recorder" AND "atrial fibrillation" detection',
        '"conduction system pacing" OR "left bundle branch pacing"',
        '"wearable cardioverter defibrillator"',
    ],
    'Guias y Consenso': [
        '"ESC guidelines" AND "atrial fibrillation"',
        '"ESC guidelines" AND "ventricular arrhythmias"',
        '"AHA ACC" AND guidelines AND arrhythmia',
        '"EHRA consensus" AND ablation',
        '"expert consensus" AND electrophysiology',
    ],
    'Investigacion Emergente': [
        '"atrial fibrillation" AND "machine learning"',
        '"ECG" AND "artificial intelligence" AND arrhythmia',
        '"digital health" AND "atrial fibrillation" detection',
        '"remote monitoring" AND arrhythmia',
        '"deep learning" AND "cardiac arrhythmia"',
    ],
}

# Revistas de alto impacto en EP
HIGH_IMPACT_JOURNALS = [
    'circulation', 'jacc', 'european heart journal', 'heart rhythm',
    'jama cardiology', 'new england journal', 'europace', 'nature medicine',
    'lancet', 'journal of the american college of cardiology',
    'circulation: arrhythmia', 'ep europace',
]

# Palabras clave que sugieren RCT o guía (→ candidatos a "cambia práctica")
RCT_SIGNALS = ['randomized', 'randomised', 'trial', 'rct', 'pivotal']
GUIDELINE_SIGNALS = ['guideline', 'consensus', 'recommendation', 'position statement']

# Emojis y colores por área
AREA_CONFIG = {
    'Fibrilacion Auricular':    {'emoji': '🔴', 'color': '#c0392b', 'bg': '#fdecea', 'id': 'fa'},
    'Taquicardia Ventricular':  {'emoji': '🟠', 'color': '#e67e22', 'bg': '#fef3e2', 'id': 'tv'},
    'TSV y Vias Accesorias':    {'emoji': '🟡', 'color': '#d4ac0d', 'bg': '#fefde7', 'id': 'tsv'},
    'Dispositivos Cardiacos':   {'emoji': '🔵', 'color': '#2980b9', 'bg': '#eaf3fb', 'id': 'disp'},
    'Guias y Consenso':         {'emoji': '🟢', 'color': '#27ae60', 'bg': '#e8f8f0', 'id': 'guias'},
    'Investigacion Emergente':  {'emoji': '🟣', 'color': '#8e44ad', 'bg': '#f3e8ff', 'id': 'ia'},
}

# =============================================================================
# BÚSQUEDA EUROPE PMC
# =============================================================================

def search_europe_pmc(query, from_date=None, to_date=None, max_results=20):
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    if from_date and to_date:
        query += f" AND FIRST_PDATE:[{from_date} TO {to_date}]"
    params = {
        'query': query, 'format': 'json', 'resultType': 'core',
        'pageSize': max_results, 'page': 1, 'sortOrder': 'FIRST_PDATE_DESC',
    }
    try:
        r = requests.get(base_url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if 'resultList' in data and 'result' in data['resultList']:
            return data['resultList']['result']
        return []
    except Exception as e:
        print(f"Error en búsqueda: {e}")
        return []


def extract_paper_info(paper):
    abstract = paper.get('abstractText', '')
    abstract_short = (abstract[:600] + '…') if len(abstract) > 600 else abstract
    title = paper.get('title', 'Sin título').strip()
    # Limpiar tags HTML del título
    title = re.sub(r'<[^>]+>', '', title)
    journal = paper.get('journalTitle', 'N/A')
    authors = paper.get('authorString', 'N/A')
    doi = paper.get('doi', '')
    return {
        'title': title,
        'authors': authors,
        'journal': journal,
        'year': paper.get('pubYear', 'N/A'),
        'doi': doi,
        'pmid': paper.get('pmid', ''),
        'abstract': abstract_short,
        'abstract_full': abstract,
        'url': paper.get('sourceUrl', f"https://doi.org/{doi}" if doi else '#'),
        'publication_date': paper.get('firstPublicationDate', 'N/A'),
        'is_open_access': paper.get('isOpenAccess', 'N') == 'Y',
        'is_high_impact': any(j in journal.lower() for j in HIGH_IMPACT_JOURNALS),
        'is_rct': any(s in (paper.get('title', '') + abstract).lower() for s in RCT_SIGNALS),
        'is_guideline': any(s in (paper.get('title', '') + abstract).lower() for s in GUIDELINE_SIGNALS),
    }


# =============================================================================
# CLASIFICACIÓN DE PAPERS POR ÁREA
# =============================================================================

def classify_papers_by_area(all_papers):
    """Asigna cada paper a su área según keywords. Un paper puede aparecer en varias."""
    classified = {area: [] for area in KEYWORDS}
    seen_by_area = {area: set() for area in KEYWORDS}

    for paper in all_papers:
        doi = paper.get('doi', paper.get('pmid', ''))
        title_abstract = (paper.get('title', '') + ' ' + paper.get('abstractText', '')).lower()
        for area, kws in KEYWORDS.items():
            for kw in kws:
                # Extraer término principal del keyword
                term = kw.split(' AND ')[0].replace('"', '').strip().lower()
                if term in title_abstract and doi not in seen_by_area[area]:
                    classified[area].append(paper)
                    seen_by_area[area].add(doi)
                    break
    return classified


def pick_paper_of_week(all_papers):
    """Elige el paper de la semana: RCT en revista de alto impacto, o primer alto impacto."""
    rct_hi = [p for p in all_papers
              if any(j in p.get('journalTitle', '').lower() for j in HIGH_IMPACT_JOURNALS)
              and any(s in (p.get('title', '') + p.get('abstractText', '')).lower() for s in RCT_SIGNALS)]
    if rct_hi:
        return rct_hi[0]
    hi = [p for p in all_papers
          if any(j in p.get('journalTitle', '').lower() for j in HIGH_IMPACT_JOURNALS)]
    return hi[0] if hi else (all_papers[0] if all_papers else None)


def is_practice_changing(info):
    """Determina si un paper es candidato a cambiar práctica."""
    return info['is_rct'] or info['is_guideline'] or info['is_high_impact']


# =============================================================================
# GENERACIÓN HTML — BLOG CLÍNICO EP
# =============================================================================

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fa; color: #2d3748; font-size: 1.02em; line-height: 1.7; }
header { background: linear-gradient(135deg, #c0392b, #7b241c); color: white; padding: 40px 20px 30px; text-align: center; }
header .label { font-size: 0.72em; text-transform: uppercase; letter-spacing: 2px; opacity: 0.7; margin-bottom: 10px; }
header h1 { font-size: 1.9em; font-weight: 800; margin-bottom: 10px; line-height: 1.2; }
header .subtitle { opacity: 0.85; font-size: 0.9em; }
header .author { font-size: 0.76em; margin-top: 10px; opacity: 0.6; }
.toc { background: white; max-width: 960px; margin: 22px auto 0; border-radius: 12px; padding: 16px 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.toc h3 { font-size: 0.76em; text-transform: uppercase; letter-spacing: 1px; color: #a0aec0; margin-bottom: 8px; }
.toc-links { display: flex; flex-wrap: wrap; gap: 7px; }
.toc-links a { font-size: 0.8em; color: #c0392b; text-decoration: none; background: #fdecea; padding: 3px 11px; border-radius: 20px; font-weight: 600; }
.toc-links a:hover { background: #f9c6c3; }
.back-link { display:inline-block; margin: 18px 20px 0; font-size:0.82em; color:#c0392b; text-decoration:none; font-weight:600; }
main { max-width: 960px; margin: 22px auto 40px; padding: 0 20px; }
.stat-row { display: flex; gap: 10px; margin-bottom: 26px; flex-wrap: wrap; }
.stat-box { background: white; border-radius: 10px; padding: 13px 14px; flex: 1; min-width: 110px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); text-align: center; }
.stat-box .num { font-size: 1.8em; font-weight: 800; color: #c0392b; }
.stat-box .lbl { font-size: 0.7em; color: #718096; margin-top: 2px; }
.section-title { font-size: 1.2em; font-weight: 800; margin: 34px 0 14px; padding-bottom: 9px; border-bottom: 3px solid; display: flex; align-items: center; gap: 10px; }
.editorial { background: white; border-radius: 12px; padding: 28px 30px; margin-bottom: 26px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); border-left: 5px solid #c0392b; }
.editorial .ed-label { font-size: 0.7em; text-transform: uppercase; letter-spacing: 1.5px; color: #c0392b; font-weight: 700; margin-bottom: 10px; }
.editorial h2 { font-size: 1.2em; font-weight: 800; color: #1a202c; margin-bottom: 14px; }
.editorial p { color: #4a5568; margin-bottom: 10px; font-size: 0.93em; }
.potw { background: linear-gradient(135deg,#fff5f5,#fff); border: 2px solid #e8b4b8; border-radius: 14px; padding: 28px; margin-bottom: 26px; }
.potw-badge { display:inline-block; background:#c0392b; color:white; font-size:0.7em; font-weight:700; text-transform:uppercase; letter-spacing:1px; padding:3px 11px; border-radius:20px; margin-bottom:14px; }
.potw h2 { font-size:1.1em; font-weight:800; color:#1a202c; margin-bottom:5px; line-height:1.4; }
.potw .citation { font-size:0.76em; color:#718096; margin-bottom:18px; }
.potw-section { margin-bottom:16px; }
.potw-section h4 { font-size:0.76em; text-transform:uppercase; letter-spacing:1px; color:#c0392b; font-weight:700; margin-bottom:5px; }
.potw-section p, .potw-section ul { font-size:0.88em; color:#4a5568; }
.potw-section ul { padding-left:16px; }
.potw-section li { margin-bottom:3px; }
.thm { background:#1a202c; color:white; border-radius:9px; padding:14px 18px; margin-top:16px; }
.thm .thm-label { font-size:0.68em; text-transform:uppercase; letter-spacing:1px; color:#e2b4b4; margin-bottom:5px; }
.thm p { font-size:0.86em; line-height:1.6; }
.practice-box { margin-top:12px; border-radius:9px; padding:12px 16px; }
.practice-yes { background:#e8f8f0; border-left:4px solid #27ae60; }
.practice-no  { background:#fef3e2; border-left:4px solid #e67e22; }
.practice-box .pb-label { font-size:0.7em; text-transform:uppercase; letter-spacing:1px; font-weight:700; margin-bottom:3px; }
.practice-yes .pb-label { color:#27ae60; }
.practice-no  .pb-label { color:#e67e22; }
.practice-box p { font-size:0.86em; color:#4a5568; }
.paper { border:1px solid #edf2f7; border-radius:10px; padding:18px 20px; margin-bottom:14px; background:#fdfdfd; }
.paper:last-child { margin-bottom:0; }
.paper h3 { font-size:0.95em; font-weight:700; color:#1a202c; margin-bottom:5px; line-height:1.45; }
.paper .meta { font-size:0.75em; color:#718096; margin-bottom:8px; }
.paper .meta span { margin-right:10px; }
.paper .body { font-size:0.87em; color:#4a5568; line-height:1.65; margin-bottom:10px; }
.paper .body strong { color:#2d3748; }
.paper-foot { display:flex; gap:7px; align-items:center; flex-wrap:wrap; }
.tag { display:inline-block; border-radius:10px; padding:2px 8px; font-size:0.68em; font-weight:700; }
.tag-rct    { background:#e8f8f0; color:#1e8449; }
.tag-obs    { background:#eaf3fb; color:#1a5276; }
.tag-meta   { background:#f3e8ff; color:#6c3483; }
.tag-review { background:#fef9e7; color:#7d6608; }
.tag-guia   { background:#e8f8f0; color:#1e8449; }
.tag-oa     { background:#e8f8f0; color:#1e8449; }
.tag-pay    { background:#fdecea; color:#922b21; }
.doi-link   { font-size:0.75em; color:#c0392b; text-decoration:none; font-weight:700; margin-left:auto; }
.doi-link:hover { text-decoration:underline; }
.mini-thm { background:#f8f4ff; border-left:3px solid #8e44ad; border-radius:6px; padding:7px 11px; margin-top:8px; font-size:0.8em; color:#4a3060; font-style:italic; }
.mini-thm::before { content:'💡 '; }
.card { background:white; border-radius:12px; padding:24px; margin-bottom:18px; box-shadow:0 2px 8px rgba(0,0,0,0.07); }
.quick-item { padding:10px 0; border-bottom:1px solid #f0f0f0; display:flex; gap:12px; align-items:flex-start; }
.quick-item:last-child { border-bottom:none; }
.quick-dot { width:7px; height:7px; border-radius:50%; background:#c0392b; flex-shrink:0; margin-top:9px; }
.quick-item p { font-size:0.86em; color:#4a5568; }
.quick-item p strong { color:#1a202c; }
.cp-item { background:white; border-radius:10px; padding:14px 18px; margin-bottom:9px; box-shadow:0 1px 4px rgba(0,0,0,0.06); display:flex; gap:12px; align-items:flex-start; }
.cp-si { border-left:4px solid #27ae60; }
.cp-no { border-left:4px solid #e67e22; }
.cp-badge { font-size:0.68em; font-weight:800; text-transform:uppercase; padding:3px 9px; border-radius:10px; flex-shrink:0; margin-top:2px; }
.cp-si .cp-badge { background:#e8f8f0; color:#1e8449; }
.cp-no  .cp-badge { background:#fef3e2; color:#a04000; }
.cp-item p { font-size:0.86em; color:#4a5568; }
.cp-item p strong { color:#1a202c; }
footer { text-align:center; padding:32px 20px; font-size:0.77em; color:#a0aec0; }
footer a { color:#c0392b; text-decoration:none; }
@media (max-width:640px) { header h1 { font-size:1.4em; } .potw { padding:18px; } }
"""


def _tag(info):
    tags = []
    if info['is_rct']:        tags.append('<span class="tag tag-rct">RCT</span>')
    elif info['is_guideline']: tags.append('<span class="tag tag-guia">Guía/Consenso</span>')
    else:                      tags.append('<span class="tag tag-obs">Observacional</span>')
    if info['is_open_access']:
        tags.append('<span class="tag tag-oa">✅ Open Access</span>')
    else:
        tags.append('<span class="tag tag-pay">🔒 Acceso restringido</span>')
    return ' '.join(tags)


def _doi_link(info):
    if info['doi']:
        url = f"https://doi.org/{info['doi']}"
        short = info['doi'][:40] + ('…' if len(info['doi']) > 40 else '')
        return f'<a class="doi-link" href="{url}" target="_blank">🔗 {short}</a>'
    return ''


def build_paper_card(paper):
    info = extract_paper_info(paper)
    authors_short = info['authors'][:90] + ('…' if len(info['authors']) > 90 else '')
    abstract_html = info['abstract'].replace('<', '&lt;').replace('>', '&gt;') if info['abstract'] else ''
    thm = ''
    if abstract_html:
        thm = f'<div class="mini-thm">{abstract_html[:200]}{"…" if len(abstract_html) > 200 else ""}</div>'
    return f"""
<div class="paper">
  <h3>{info['title']}</h3>
  <div class="meta">
    <span>✍️ {authors_short}</span>
    <span>📰 {info['journal']}</span>
    <span>📅 {info['publication_date']}</span>
  </div>
  <div class="body">{abstract_html}</div>
  {thm}
  <div class="paper-foot">
    {_tag(info)}
    {_doi_link(info)}
  </div>
</div>"""


def build_potw_section(paper):
    """Construye la sección Paper de la Semana con análisis detallado."""
    info = extract_paper_info(paper)
    authors_short = info['authors'][:100] + ('…' if len(info['authors']) > 100 else '')
    abstract_html = info['abstract_full'].replace('<', '&lt;').replace('>', '&gt;') if info['abstract_full'] else 'Abstract no disponible.'
    doi_url = f"https://doi.org/{info['doi']}" if info['doi'] else info['url']

    practice_label = '✅ Sí — candidato a cambiar práctica' if is_practice_changing(info) else '🟡 Requiere valoración individual'
    practice_class = 'practice-yes' if is_practice_changing(info) else 'practice-no'
    pb_label = '✅ Cambia práctica' if is_practice_changing(info) else '🟡 Valorar individualmente'
    practice_text = ('RCT en revista de alto impacto — datos con nivel de evidencia suficiente para modificar práctica clínica.'
                     if is_practice_changing(info) else
                     'Estudio observacional o registro. Apoya tendencias pero requiere confirmación en ensayos aleatorizados.')

    return f"""
<div class="potw" id="potw">
  <div class="potw-badge">⭐ Paper de la semana</div>
  <h2>{info['title']}</h2>
  <p class="citation">{authors_short} — <em>{info['journal']}</em> {info['year']} · <a href="{doi_url}" target="_blank" style="color:#c0392b;">doi:{info['doi'] or 'ver enlace'}</a></p>

  <div class="potw-section">
    <h4>📰 Contexto clínico</h4>
    <p>Publicado en <strong>{info['journal']}</strong> el {info['publication_date']}. {'Acceso abierto ✅' if info['is_open_access'] else 'Acceso restringido 🔒'}. {'Ensayo aleatorizado o trial.' if info['is_rct'] else 'Guía o documento de consenso.' if info['is_guideline'] else 'Estudio observacional / registro.'}</p>
  </div>

  <div class="potw-section">
    <h4>📋 Abstract completo</h4>
    <p>{abstract_html}</p>
  </div>

  <div class="thm">
    <div class="thm-label">Take Home Message</div>
    <p>{abstract_html[:300]}{"…" if len(abstract_html) > 300 else ""}</p>
  </div>

  <div class="practice-box {practice_class}">
    <div class="pb-label">{pb_label}</div>
    <p>{practice_text}</p>
  </div>
</div>"""


def build_area_section(area, papers, config):
    if not papers:
        return ''
    color = config['color']
    bg = config['bg']
    emoji = config['emoji']
    section_id = config['id']
    cards = ''.join(build_paper_card(p) for p in papers[:6])
    return f"""
<h2 class="section-title" id="{section_id}" style="color:{color}; border-color:{color};">
  {emoji} {area} <span style="font-size:0.6em;font-weight:400;color:#a0aec0;margin-left:8px;">{len(papers)} papers</span>
</h2>
<div style="margin-bottom:28px;">
  {cards}
</div>"""


def build_quick_hits(quick_papers):
    if not quick_papers:
        return ''
    items = ''
    for p in quick_papers[:8]:
        info = extract_paper_info(p)
        doi_url = f"https://doi.org/{info['doi']}" if info['doi'] else info['url']
        abstract_snippet = info['abstract'][:180].replace('<', '&lt;').replace('>', '&gt;') + '…' if info['abstract'] else ''
        items += f"""
<div class="quick-item">
  <div class="quick-dot"></div>
  <p><strong><a href="{doi_url}" target="_blank" style="color:#1a202c;text-decoration:none;">{info['title'][:100]}{'…' if len(info['title'])>100 else ''}</a></strong>
  — {abstract_snippet} <em style="color:#a0aec0;">({info['journal']}, {info['publication_date']})</em></p>
</div>"""
    return f"""
<h2 class="section-title quick" id="quick" style="color:#566573;border-color:#566573;">
  ⚡ Quick Hits
</h2>
<div class="card">{items}</div>"""


def build_practica_section(practice_papers, all_papers_infos):
    items = ''
    for info in practice_papers[:6]:
        doi_url = f"https://doi.org/{info['doi']}" if info['doi'] else '#'
        tipo = 'RCT' if info['is_rct'] else ('Guía' if info['is_guideline'] else 'Alto impacto')
        items += f"""
<div class="cp-item cp-si">
  <span class="cp-badge">✅ Sí</span>
  <p><strong><a href="{doi_url}" target="_blank" style="color:#1a202c;text-decoration:none;">{info['title'][:100]}{'…' if len(info['title'])>100 else ''}</a></strong>
  ({tipo} · {info['journal']}) — {info['abstract'][:180].replace('<','&lt;').replace('>','&gt;')}…</p>
</div>"""
    if not items:
        items = '<p style="font-size:0.88em;color:#718096;padding:10px;">No se identificaron papers con criterios de cambio de práctica esta semana.</p>'
    return f"""
<h2 class="section-title practica" id="practica" style="color:#c0392b;border-color:#c0392b;">
  ✅ ¿Cambia mi práctica esta semana?
</h2>
<div style="margin-bottom:28px;">{items}</div>"""


def generate_blog_reporte(all_papers, week_start_date, week_end_date):
    """Genera el HTML completo del blog clínico semanal."""
    classified = classify_papers_by_area(all_papers)
    potw_paper = pick_paper_of_week(all_papers)
    potw_doi = potw_paper.get('doi', '') if potw_paper else ''

    # Papers para quick hits: los que no son de alto impacto ni principales
    main_papers_set = set()
    for papers in classified.values():
        for p in papers[:4]:
            main_papers_set.add(p.get('doi', p.get('pmid', '')))
    quick_papers = [p for p in all_papers
                    if p.get('doi', p.get('pmid', '')) not in main_papers_set][:8]

    # Papers candidatos a cambiar práctica
    practice_infos = [extract_paper_info(p) for p in all_papers if is_practice_changing(extract_paper_info(p))][:6]

    # Stats
    n_oa = sum(1 for p in all_papers if p.get('isOpenAccess', 'N') == 'Y')
    n_rct = sum(1 for p in all_papers if any(s in (p.get('title','') + p.get('abstractText','')).lower() for s in RCT_SIGNALS))
    n_guide = sum(1 for p in all_papers if any(s in (p.get('title','') + p.get('abstractText','')).lower() for s in GUIDELINE_SIGNALS))

    week_str = f"{week_start_date.strftime('%-d')} al {week_end_date.strftime('%-d de %B de %Y')}"
    generated = datetime.now().strftime('%d/%m/%Y %H:%M')

    # TOC
    toc_items = ''.join(
        f'<a href="#{cfg["id"]}">{cfg["emoji"]} {area}</a>'
        for area, cfg in AREA_CONFIG.items()
        if classified.get(area)
    )
    toc_items += '<a href="#quick">⚡ Quick Hits</a><a href="#practica">✅ ¿Cambia mi práctica?</a>'

    # Editorial automático
    top_journals = list({p.get('journalTitle','') for p in all_papers if any(j in p.get('journalTitle','').lower() for j in HIGH_IMPACT_JOURNALS)})[:3]
    top_journals_str = ', '.join(f'<em>{j}</em>' for j in top_journals) if top_journals else 'diversas revistas del área'
    editorial_html = f"""
<div class="editorial" id="editorial">
  <div class="ed-label">📝 Editorial semanal</div>
  <h2>Semana del {week_str}</h2>
  <p>Esta semana el agente bibliográfico ha identificado <strong>{len(all_papers)} nuevas publicaciones</strong> en arritmias y electrofisiología, con presencia destacada en {top_journals_str}. Se han cubierto {len([a for a,ps in classified.items() if ps])} áreas temáticas, con {n_rct} ensayos aleatorizados o trials y {n_guide} documentos de guías o consenso.</p>
  <p>{'El paper de la semana es: <strong>' + (potw_paper.get('title','') if potw_paper else '') + '</strong>, seleccionado por combinar alto impacto en revista de referencia con diseño de estudio prospectivo o aleatorizado.' if potw_paper else 'No se identificó un paper de la semana con criterios de alto impacto.'}</p>
  <p>Revisa la sección <a href="#practica" style="color:#c0392b;font-weight:600;">¿Cambia mi práctica?</a> al final del reporte para un resumen accionable de los hallazgos más relevantes de esta edición.</p>
</div>"""

    # POTW
    potw_html = build_potw_section(potw_paper) if potw_paper else ''

    # Secciones por área
    sections_html = ''
    for area, config in AREA_CONFIG.items():
        sections_html += build_area_section(area, classified.get(area, []), config)

    quick_html = build_quick_hits(quick_papers)
    practica_html = build_practica_section(practice_infos, [extract_paper_info(p) for p in all_papers])

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Revista Semanal EP — {week_str}</title>
  <style>{CSS}</style>
</head>
<body>

<header>
  <div class="label">Revista Semanal de Electrofisiología</div>
  <h1>Arritmias &amp; Electrofisiología<br><span style="font-weight:400;font-size:0.65em;">Semana del {week_str}</span></h1>
  <p class="subtitle">Revisión bibliográfica automática · Europe PMC · {len(KEYWORDS)} áreas EP</p>
  <p class="author">Dr. Santiago Martín Gomero · Electrofisiología Cardíaca · Las Palmas de Gran Canaria</p>
  <p class="author">Generado el {generated}</p>
</header>

<a class="back-link" href="../index.html">← Volver al inicio</a>

<div class="toc">
  <h3>Contenido de esta edición</h3>
  <div class="toc-links">
    <a href="#editorial">📝 Editorial</a>
    <a href="#potw">⭐ Paper de la semana</a>
    {toc_items}
  </div>
</div>

<main>
  <div class="stat-row">
    <div class="stat-box"><div class="num">{len(all_papers)}</div><div class="lbl">Papers esta semana</div></div>
    <div class="stat-box"><div class="num">{n_oa}</div><div class="lbl">Open Access</div></div>
    <div class="stat-box"><div class="num">{len([a for a,ps in classified.items() if ps])}</div><div class="lbl">Áreas cubiertas</div></div>
    <div class="stat-box"><div class="num">{n_rct}</div><div class="lbl">RCTs / Trials</div></div>
    <div class="stat-box"><div class="num">{n_guide}</div><div class="lbl">Guías / Consensos</div></div>
    <div class="stat-box"><div class="num">{len(practice_infos)}</div><div class="lbl">Práctica cambiante</div></div>
  </div>

  {editorial_html}
  {potw_html}
  {sections_html}
  {quick_html}
  {practica_html}
</main>

<footer>
  <p>Revisión bibliográfica semanal generada automáticamente por el Agente de Arritmias</p>
  <p style="margin-top:7px;">
    <a href="../index.html">🫀 Inicio</a> &nbsp;|&nbsp;
    <a href="./index.html">📂 Todos los reportes</a> &nbsp;|&nbsp;
    <a href="https://github.com/Santiagomartingomero/agente-arritmias-literatura-">💻 GitHub</a>
  </p>
  <p style="margin-top:5px;">Dr. Santiago Martín Gomero · Electrofisiología Cardíaca · Las Palmas de Gran Canaria</p>
</footer>
</body>
</html>"""

    return html


# =============================================================================
# ACTUALIZAR ÍNDICE DE REPORTES
# =============================================================================

def update_reportes_index(from_date_str):
    """Regenera reportes/index.html añadiendo la semana actual."""
    index_path = 'reportes/index.html'
    entries = []

    # Leer entradas existentes desde archivos HTML generados
    if os.path.exists('reportes'):
        html_files = sorted(
            [f for f in os.listdir('reportes') if f.startswith('reporte_') and f.endswith('.html')],
            reverse=True
        )
        for f in html_files:
            date_str = f.replace('reporte_', '').replace('.html', '')
            entries.append(date_str)

    cards_html = ''
    for date_str in entries:
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d')
            label = f"Semana del {d.strftime('%-d de %B de %Y')}"
        except Exception:
            label = date_str
        cards_html += f"""
  <a class="card" href="./reporte_{date_str}.html">
    <div class="card-info">
      <h3>📋 {label}</h3>
      <p>Generado automáticamente · Europe PMC</p>
    </div>
    <div style="font-size:1.3em;color:#c0392b;">→</div>
  </a>"""

    if not cards_html:
        cards_html = '<p style="text-align:center;color:#a0aec0;padding:30px;font-size:0.85em;">Los reportes aparecerán aquí cada lunes.</p>'

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>📂 Historial de Reportes EP</title>
  <style>
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f5f7fa; color:#2d3748; }}
    header {{ background:linear-gradient(135deg,#c0392b,#922b21); color:white; padding:32px 20px; text-align:center; }}
    header h1 {{ font-size:1.5em; margin-bottom:7px; }}
    header p {{ opacity:.85; font-size:.88em; }}
    .back-link {{ display:inline-block; margin:18px 20px 0; font-size:.82em; color:#c0392b; text-decoration:none; font-weight:600; }}
    main {{ max-width:720px; margin:20px auto; padding:0 20px 40px; }}
    .card {{ background:white; border-radius:12px; padding:20px 22px; margin-bottom:14px; box-shadow:0 2px 8px rgba(0,0,0,.07); display:flex; align-items:center; justify-content:space-between; gap:14px; text-decoration:none; color:inherit; transition:box-shadow .15s; }}
    .card:hover {{ box-shadow:0 4px 16px rgba(192,57,43,.15); }}
    .card-info h3 {{ font-size:.95em; color:#2d3748; margin-bottom:4px; }}
    .card-info p {{ font-size:.78em; color:#718096; }}
    footer {{ text-align:center; padding:22px; font-size:.77em; color:#a0aec0; }}
    footer a {{ color:#c0392b; text-decoration:none; }}
  </style>
</head>
<body>
<header>
  <h1>📂 Historial de Reportes Semanales</h1>
  <p>Archivo completo · Actualizado cada lunes automáticamente</p>
</header>
<a class="back-link" href="../index.html">← Volver al inicio</a>
<main>
  {cards_html}
</main>
<footer>
  <a href="../index.html">🫀 Inicio</a> &nbsp;|&nbsp;
  <a href="https://github.com/Santiagomartingomero/agente-arritmias-literatura-/tree/main/reportes">💻 GitHub</a>
</footer>
</body>
</html>"""

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"reportes/index.html actualizado con {len(entries)} entradas")


# =============================================================================
# REPORTE MARKDOWN (mantenido para compatibilidad)
# =============================================================================

def generate_weekly_report(all_papers, week_start_date):
    high_impact = [p for p in all_papers if any(
        j in p.get('journalTitle', '').lower() for j in HIGH_IMPACT_JOURNALS
    )]
    report = f"""# Reporte Semanal — Arritmias y Electrofisiología
**Semana del**: {week_start_date.strftime('%d %B %Y')}
**Generado**: {datetime.now().strftime('%d %B %Y, %H:%M')}

---

## Resumen Ejecutivo
- **Total papers encontrados**: {len(all_papers)}
- **Áreas monitorizadas**: {len(KEYWORDS)}
- **Revistas de alto impacto**: {len(high_impact)}

---

"""
    for category, keywords in KEYWORDS.items():
        category_papers = [
            p for p in all_papers
            if any(kw.split(' AND ')[0].strip('"').lower() in p.get('title', '').lower() for kw in keywords)
        ]
        if category_papers:
            report += f"## {category}\n\n"
            for i, paper in enumerate(category_papers[:5], 1):
                info = extract_paper_info(paper)
                doi_link = f"[{info['doi']}](https://doi.org/{info['doi']})" if info['doi'] else 'N/A'
                report += f"""### {i}. {info['title']}
**Autores**: {info['authors']}
**Revista**: *{info['journal']}* ({info['year']})
**DOI**: {doi_link}
**Fecha**: {info['publication_date']}

{info['abstract']}

---

"""
    report += "*Generado automáticamente con Europe PMC API*\n"
    return report


# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================

def run_weekly_search():
    to_date = datetime.now()
    from_date = to_date - timedelta(days=7)
    from_date_str = from_date.strftime('%Y-%m-%d')
    to_date_str = to_date.strftime('%Y-%m-%d')

    print(f"Iniciando búsqueda semanal...")
    print(f"Periodo: {from_date_str} → {to_date_str}\n")

    all_papers = []
    for category, keywords in KEYWORDS.items():
        print(f"Buscando: {category}")
        for keyword in keywords:
            papers = search_europe_pmc(
                query=keyword,
                from_date=from_date_str,
                to_date=to_date_str,
                max_results=10
            )
            all_papers.extend(papers)
            print(f"  {keyword[:60]}… → {len(papers)} papers")

    # Deduplicar por DOI
    unique_papers, seen_dois = [], set()
    for paper in all_papers:
        doi = paper.get('doi', '') or paper.get('pmid', '')
        if doi and doi not in seen_dois:
            unique_papers.append(paper)
            seen_dois.add(doi)

    print(f"\nTotal papers únicos: {len(unique_papers)}")

    if unique_papers:
        os.makedirs('reportes', exist_ok=True)

        # 1. Markdown (compatibilidad)
        report_md = generate_weekly_report(unique_papers, from_date)
        fn_md = f'reportes/reporte_arritmias_{from_date_str}.md'
        with open(fn_md, 'w', encoding='utf-8') as f:
            f.write(report_md)
        print(f"Markdown: {fn_md}")

        # 2. JSON
        fn_json = f'reportes/reporte_arritmias_{from_date_str}.json'
        with open(fn_json, 'w', encoding='utf-8') as f:
            json.dump(unique_papers, f, indent=2, ensure_ascii=False)
        print(f"JSON: {fn_json}")

        # 3. Blog HTML detallado ← NUEVO
        blog_html = generate_blog_reporte(unique_papers, from_date, to_date)
        fn_html = f'reportes/reporte_{from_date_str}.html'
        with open(fn_html, 'w', encoding='utf-8') as f:
            f.write(blog_html)
        print(f"Blog HTML: {fn_html}")

        # 4. Actualizar índice de reportes ← NUEVO
        update_reportes_index(from_date_str)
        print("Índice de reportes actualizado")

        # 5. README
        readme = f"""# Agente de Revisión Bibliográfica en Arritmias

![Última actualización](https://img.shields.io/badge/último_reporte-{from_date_str}-blue)
![Papers](https://img.shields.io/badge/papers_semana-{len(unique_papers)}-green)

Agente automatizado que busca y resume las últimas publicaciones en arritmias y electrofisiología usando **Europe PMC API** (45M+ papers, gratuita).

Genera cada lunes un **blog clínico detallado** en formato HTML para electrofisiólogos, con análisis de papers, Take Home Messages, y sección ¿Cambia mi práctica?

## Áreas monitorizadas

| Área | Keywords principales |
|------|---------------------|
| **Fibrilación Auricular** | Ablación, PVI, OAI, anticoagulación, PFA, cryoballoon |
| **Taquicardia Ventricular** | Ablación, sustrato, ICD, SBRT, muerte súbita |
| **TSV & Vías Accesorias** | TRIN, WPW, TA focal, flutter, TRAV |
| **Dispositivos Cardíacos** | Leadless, TRC, ICD-S, LBBP, ILR |
| **Guías y Consenso** | ESC, AHA/ACC, EHRA |
| **Investigación Emergente** | ML/DL, ECG + IA, digital health |

## 🌐 Web

[santiagomartingomero.github.io/agente-arritmias-literatura-](https://santiagomartingomero.github.io/agente-arritmias-literatura-)

---
*Dr. Santiago Martín Gomero · Electrofisiología Cardíaca · Las Palmas de Gran Canaria*
"""
        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(readme)
        print("README actualizado")

        return unique_papers, report_md
    else:
        print("No se encontraron papers nuevos en este periodo.")
        return [], ""


if __name__ == "__main__":
    papers, report = run_weekly_search()
