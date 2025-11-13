import json
import os
import re
import sys
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, 'logs')

EXCLUDE_DIRS = {
    '.git', 'venv', '__pycache__', 'logs', 'backups', '.vscode', '.idea', '.pytest_cache'
}

INCLUDE_EXTS = {'.py', '.html', '.js', '.ts', '.md', '.sql', '.ps1'}


def load_diff() -> Dict:
    path = os.path.join(LOGS, 'schema_diff.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def iter_repo_files():
    for root, dirs, files in os.walk(ROOT):
        # Filtrar dirs
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in INCLUDE_EXTS:
                yield os.path.join(root, name)


def search_usage_in_file(path: str, patterns: List[re.Pattern]) -> List[str]:
    matches = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        for pat in patterns:
            if pat.search(text):
                matches.append(os.path.relpath(path, ROOT))
                break
    except Exception:
        pass
    return matches


def build_patterns(names: List[str]) -> List[re.Pattern]:
    pats = []
    for n in names:
        n_escaped = re.escape(n)
        pats.append(re.compile(r"\b" + n_escaped + r"\b"))
    return pats


def main():
    diff = load_diff()

    # Recolectar columnas candidatas a revisar (solo diferencias)
    targets = []
    for t, d in diff.get('tables_changed', {}).items():
        for c in d.get('columns_only_local', []):
            targets.append((t, c, 'only_local'))
        for c in d.get('columns_only_railway', []):
            targets.append((t, c, 'only_railway'))
        for ch in d.get('columns_changed', []):
            targets.append((t, ch['column'], 'changed'))

    # Buscar usos por nombre de columna (y por tabla.columna)
    report = []
    col_names = list({c for _, c, _ in targets})
    col_patterns = build_patterns(col_names)

    # También patrones como table.column
    table_col_names = [f"{t}.{c}" for t, c, _ in targets]
    table_col_patterns = build_patterns(table_col_names)

    # Indexación simple de archivos con algún match para acelerar
    file_hits = {}
    for path in iter_repo_files():
        hits = search_usage_in_file(path, col_patterns + table_col_patterns)
        if hits:
            file_hits[path] = True

    # Conteo por columna
    for (t, c, kind) in targets:
        name_patterns = build_patterns([c, f"{t}.{c}"])
        used_in = []
        for path in iter_repo_files():
            if path in file_hits:  # archivo ya conocido con algún match
                hits = search_usage_in_file(path, name_patterns)
                used_in.extend(hits)
        used_in = sorted(list(set(used_in)))
        report.append({
            'table': t,
            'column': c,
            'kind': kind,  # only_local, only_railway, changed
            'usage_count': len(used_in),
            'files': used_in[:20],  # limitar listado
        })

    os.makedirs(LOGS, exist_ok=True)
    out_json = os.path.join(LOGS, 'schema_usage_report.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # MD resumido
    out_md = os.path.join(ROOT, 'docs', 'DB_SCHEMA_USAGE.md')
    lines = []
    lines.append('# DB Schema Usage Report (diferencias)')
    lines.append('')
    for item in sorted(report, key=lambda x: (x['kind'], x['table'], x['column'])):
        lines.append(f"- [{item['kind']}] {item['table']}.{item['column']} -> usos: {item['usage_count']}")
        if item['files']:
            lines.append(f"  - Archivos: {', '.join(item['files'])}")
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Reporte de uso guardado en: {out_md} y {out_json}")


if __name__ == '__main__':
    main()
