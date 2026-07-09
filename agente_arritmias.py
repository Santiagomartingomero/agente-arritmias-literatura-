"""
Agente de Revisión Bibliográfica en Arritmias
Autor: Santiago Martín Gomero
Fuente: Europe PMC API (gratuita, 45M+ papers biomédicos)
"""

import requests
from datetime import datetime, timedelta
import json
import os

# =============================================================================
# CONFIGURACIÓN - Personaliza tus áreas de interés
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
        '"ventricular tachycardia" AND "artificial intelligence"',
    ],

    'Dispositivos Cardiacos': [
        '"leadless pacemaker" AND outcomes',
        '"cardiac resynchronization therapy" AND "non-responders"',
        '"subcutaneous ICD" AND "inappropriate shocks"',
        '"implantable loop recorder" AND "atrial fibrillation" detection',
        '"wearable cardioverter defibrillator"',
    ],

    'Guias y Consenso': [
        '"ESC guidelines" AND "atrial fibrillation"',
        '"ESC guidelines" AND "ventricular arrhythmias"',
        '"AHA ACC" AND guidelines AND arrhythmia',
        '"EHRA consensus" AND ablation',
    ],

    'Investigacion Emergente': [
        '"atrial fibrillation" AND "machine learning"',
        '"ECG" AND "artificial intelligence" AND arrhythmia',
        '"digital health" AND "atrial fibrillation" detection',
        '"remote monitoring" AND arrhythmia',
    ]
}

# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def search_europe_pmc(query, from_date=None, to_date=None, max_results=20):
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    if from_date and to_date:
        query += f" AND FIRST_PDATE:[{from_date} TO {to_date}]"

    params = {
        'query': query,
        'format': 'json',
        'resultType': 'core',
        'pageSize': max_results,
        'page': 1,
        'sortOrder': 'FIRST_PDATE_DESC'
    }

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        results = response.json()
        if 'resultList' in results and 'result' in results['resultList']:
            return results['resultList']['result']
        return []
    except Exception as e:
        print(f"Error en busqueda: {e}")
        return []


def extract_paper_info(paper):
    abstract = paper.get('abstractText', 'N/A')
    if len(abstract) > 500:
        abstract = abstract[:500] + '...'
    return {
        'title': paper.get('title', 'Sin titulo'),
        'authors': paper.get('authorString', 'N/A'),
        'journal': paper.get('journalTitle', 'N/A'),
        'year': paper.get('pubYear', 'N/A'),
        'doi': paper.get('doi', 'N/A'),
        'pmid': paper.get('pmid', 'N/A'),
        'abstract': abstract,
        'url': paper.get('sourceUrl', 'N/A'),
        'publication_date': paper.get('firstPublicationDate', 'N/A')
    }


def generate_weekly_report(all_papers, week_start_date):
    high_impact = [p for p in all_papers if any(
        j in p.get('journalTitle', '').lower()
        for j in ['circulation', 'jacc', 'european heart journal', 'heart rhythm', 'jama cardiology']
    )]

    report = f"""# Reporte Semanal - Arritmias y Electrofisiologia
**Semana del**: {week_start_date.strftime('%d %B %Y')}
**Generado**: {datetime.now().strftime('%d %B %Y, %H:%M')}

---

## Resumen Ejecutivo
- **Total de papers encontrados**: {len(all_papers)}
- **Areas monitorizadas**: {len(KEYWORDS.keys())}
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
                doi_link = f"[{info['doi']}](https://doi.org/{info['doi']})" if info['doi'] != 'N/A' else 'N/A'
                report += f"""### {i}. {info['title']}
**Autores**: {info['authors']}
**Revista**: *{info['journal']}* ({info['year']})
**DOI**: {doi_link}
**Fecha**: {info['publication_date']}

{info['abstract']}

[Ver paper completo]({info['url']})

---

"""

    report += """## Proximos Pasos
1. Revisar papers de alta relevancia
2. Guardar en Zotero los de interes
3. Compartir hallazgos clave con el equipo

---
*Generado automaticamente con Europe PMC API*
"""
    return report


def generate_html_page(all_papers, week_start_date):
    """Genera index.html para GitHub Pages con el último reporte."""
    now = datetime.now().strftime('%d %B %Y, %H:%M')
    week_str = week_start_date.strftime('%d %B %Y')

    high_impact = [p for p in all_papers if any(
        j in p.get('journalTitle', '').lower()
        for j in ['circulation', 'jacc', 'european heart journal', 'heart rhythm', 'jama cardiology']
    )]

    # Construir secciones HTML por categoría
    sections_html = ""
    for category, keywords in KEYWORDS.items():
        category_papers = [
            p for p in all_papers
            if any(kw.split(' AND ')[0].strip('"').lower() in p.get('title', '').lower() for kw in keywords)
        ]
        if not category_papers:
            continue

        papers_html = ""
        for paper in category_papers[:5]:
            info = extract_paper_info(paper)
            doi_url = f"https://doi.org/{info['doi']}" if info['doi'] != 'N/A' else info['url']
            abstract_text = info['abstract'] if info['abstract'] != 'N/A' else ''
            papers_html += f"""
            <div class="paper">
                <h3><a href="{doi_url}" target="_blank">{info['title']}</a></h3>
                <p class="meta">📋 <strong>{info['journal']}</strong> ({info['year']}) &nbsp;|&nbsp; 👥 {info['authors'][:80]}{'...' if len(info['authors']) > 80 else ''}</p>
                <p class="meta">📅 {info['publication_date']} &nbsp;|&nbsp; DOI: {info['doi']}</p>
                <p class="abstract">{abstract_text}</p>
            </div>"""

        sections_html += f"""
        <section class="category">
            <h2>{category} <span class="count">{len(category_papers)} papers</span></h2>
            {papers_html}
        </section>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🫀 Arritmias - Reporte Semanal</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fa; color: #2d3748; }}
    header {{ background: linear-gradient(135deg, #c0392b, #922b21); color: white; padding: 30px 20px; text-align: center; }}
    header h1 {{ font-size: 1.8em; margin-bottom: 8px; }}
    header p {{ opacity: 0.85; font-size: 0.95em; }}
    .stats {{ display: flex; justify-content: center; gap: 30px; background: white; padding: 20px; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }}
    .stat {{ text-align: center; }}
    .stat .num {{ font-size: 2em; font-weight: bold; color: #c0392b; }}
    .stat .label {{ font-size: 0.8em; color: #718096; }}
    main {{ max-width: 900px; margin: 30px auto; padding: 0 20px; }}
    .category {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }}
    .category h2 {{ color: #c0392b; font-size: 1.2em; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 2px solid #fdecea; }}
    .count {{ background: #fdecea; color: #c0392b; font-size: 0.7em; padding: 2px 8px; border-radius: 10px; margin-left: 8px; font-weight: normal; }}
    .paper {{ border-left: 3px solid #e2e8f0; padding-left: 14px; margin-bottom: 20px; }}
    .paper:last-child {{ margin-bottom: 0; }}
    .paper h3 {{ font-size: 0.95em; margin-bottom: 6px; line-height: 1.4; }}
    .paper h3 a {{ color: #2b6cb0; text-decoration: none; }}
    .paper h3 a:hover {{ text-decoration: underline; }}
    .meta {{ font-size: 0.78em; color: #718096; margin-bottom: 4px; }}
    .abstract {{ font-size: 0.82em; color: #4a5568; margin-top: 8px; line-height: 1.5; }}
    footer {{ text-align: center; padding: 30px; font-size: 0.8em; color: #a0aec0; }}
  </style>
</head>
<body>
  <header>
    <h1>🫀 Arritmias &amp; Electrofisiología</h1>
    <p>Reporte semanal · Semana del {week_str}</p>
    <p style="font-size:0.8em; margin-top:6px;">Actualizado: {now}</p>
  </header>
  <div class="stats">
    <div class="stat"><div class="num">{len(all_papers)}</div><div class="label">Papers encontrados</div></div>
    <div class="stat"><div class="num">{len(high_impact)}</div><div class="label">Alto impacto</div></div>
    <div class="stat"><div class="num">{len(KEYWORDS)}</div><div class="label">Áreas monitorizadas</div></div>
  </div>
  <main>
    {sections_html}
  </main>
  <footer>
    <p>Dr. Santiago Martín Gomero · Cardiología · Electrofisiología · Las Palmas de Gran Canaria</p>
    <p style="margin-top:6px;"><a href="https://github.com/Santiagomartingomero/agente-arritmias-literatura-">📂 Ver repositorio</a></p>
  </footer>
</body>
</html>"""

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("index.html generado para GitHub Pages")


def update_readme(latest_date, paper_count):
    reportes_list = ""
    if os.path.exists('reportes'):
        reportes = sorted([f for f in os.listdir('reportes') if f.endswith('.md')], reverse=True)[:5]
        reportes_list = "\n| Fecha | Reporte |\n|-------|---------|\n"
        for r in reportes:
            date = r.replace('reporte_arritmias_', '').replace('.md', '')
            reportes_list += f"| {date} | [Ver reporte](reportes/{r}) |\n"

    readme = f"""# Agente de Revision Bibliografica en Arritmias

![Ultima actualizacion](https://img.shields.io/badge/ultimo_reporte-{latest_date}-blue)
![Papers](https://img.shields.io/badge/papers_semana-{paper_count}-green)

Agente automatizado que busca y resume las ultimas publicaciones en arritmias y electrofisiologia usando **Europe PMC API** (45M+ papers, completamente gratuita).

## Areas monitorizadas

| Area | Keywords principales |
|------|---------------------|
| **Fibrilacion Auricular** | Ablacion, PVI, OAI, anticoagulacion, PFA, cryoballoon |
| **Taquicardia Ventricular** | Ablacion, sustrato, ICD, miocardiopatias, IA |
| **Dispositivos Cardiacos** | Leadless, TRC, ICD subcutaneo, ILR, wearable |
| **Guias y Consenso** | ESC, AHA/ACC, EHRA |
| **Investigacion Emergente** | ML/DL, ECG + IA, digital health, monitoreo remoto |

## Uso

### Automatico
Se ejecuta cada **lunes a las 8:00 AM UTC** (10:00 Canarias). Los reportes se guardan en `reportes/`.

### Manual
1. Ve a **Actions** -> **Revision Semanal Arritmias**
2. Click en **Run workflow**
3. Espera ~2-3 minutos

## Ultimos reportes
{reportes_list}

## Instalacion local

```bash
git clone https://github.com/Santiagomartingomero/agente-arritmias-literatura-.git
cd agente-arritmias-literatura-
pip install -r requirements.txt
python agente_arritmias.py
```

---
*Desarrollado por Santiago Martin Gomero - Cardiologo en formacion, Electrofisiologia*
"""

    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    print("README actualizado")


def run_weekly_search():
    to_date = datetime.now()
    from_date = to_date - timedelta(days=7)
    from_date_str = from_date.strftime('%Y-%m-%d')
    to_date_str = to_date.strftime('%Y-%m-%d')

    print(f"Iniciando busqueda semanal...")
    print(f"Periodo: {from_date_str} a {to_date_str}\n")

    all_papers = []

    for category, keywords in KEYWORDS.items():
        print(f"Buscando en: {category}")
        for keyword in keywords:
            papers = search_europe_pmc(
                query=keyword,
                from_date=from_date_str,
                to_date=to_date_str,
                max_results=10
            )
            all_papers.extend(papers)
            print(f"  {keyword[:60]}... -> {len(papers)} papers")

    # Eliminar duplicados por DOI
    unique_papers = []
    seen_dois = set()
    for paper in all_papers:
        doi = paper.get('doi', '')
        if doi and doi not in seen_dois:
            unique_papers.append(paper)
            seen_dois.add(doi)

    print(f"\nBusqueda completada! Total papers unicos: {len(unique_papers)}")

    if unique_papers:
        os.makedirs('reportes', exist_ok=True)

        report = generate_weekly_report(unique_papers, from_date)

        filename_md = f'reportes/reporte_arritmias_{from_date_str}.md'
        with open(filename_md, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Reporte guardado: {filename_md}")

        filename_json = f'reportes/reporte_arritmias_{from_date_str}.json'
        with open(filename_json, 'w', encoding='utf-8') as f:
            json.dump(unique_papers, f, indent=2, ensure_ascii=False)
        print(f"JSON guardado: {filename_json}")

        # Generar index.html para GitHub Pages
        generate_html_page(unique_papers, from_date)

        update_readme(from_date_str, len(unique_papers))

        return unique_papers, report
    else:
        print("No se encontraron papers nuevos en este periodo.")
        return [], ""


if __name__ == "__main__":
    papers, report = run_weekly_search()
