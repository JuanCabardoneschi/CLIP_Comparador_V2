import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_schema(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['schema']


def compare_schemas(local, remote):
    diff = {
        'tables_only_local': [],
        'tables_only_railway': [],
        'tables_changed': {},
    }

    local_tables = set(local.keys())
    remote_tables = set(remote.keys())

    diff['tables_only_local'] = sorted(list(local_tables - remote_tables))
    diff['tables_only_railway'] = sorted(list(remote_tables - local_tables))

    for t in sorted(local_tables & remote_tables):
        lcols = {c['name']: c for c in local[t]}
        rcols = {c['name']: c for c in remote[t]}

        only_local = sorted([c for c in lcols.keys() if c not in rcols])
        only_remote = sorted([c for c in rcols.keys() if c not in lcols])

        changed = []
        for col in sorted(lcols.keys() & rcols.keys()):
            l = lcols[col]
            r = rcols[col]
            # Comparamos tipo, nullability y default
            changes = {}
            if (l.get('type') != r.get('type')):
                changes['type'] = {'local': l.get('type'), 'railway': r.get('type')}
            if (bool(l.get('nullable')) != bool(r.get('nullable'))):
                changes['nullable'] = {'local': l.get('nullable'), 'railway': r.get('nullable')}
            if ((l.get('default') or '') != (r.get('default') or '')):
                changes['default'] = {'local': l.get('default'), 'railway': r.get('default')}
            if changes:
                changed.append({'column': col, 'changes': changes})

        if only_local or only_remote or changed:
            diff['tables_changed'][t] = {
                'columns_only_local': only_local,
                'columns_only_railway': only_remote,
                'columns_changed': changed,
            }

    return diff


def save_markdown(diff, out_path):
    lines = []
    lines.append('# DB Schema Diff (local vs railway)')
    lines.append('')

    if diff['tables_only_local']:
        lines.append('## Tablas solo en LOCAL')
        for t in diff['tables_only_local']:
            lines.append(f'- {t}')
        lines.append('')

    if diff['tables_only_railway']:
        lines.append('## Tablas solo en RAILWAY')
        for t in diff['tables_only_railway']:
            lines.append(f'- {t}')
        lines.append('')

    if diff['tables_changed']:
        lines.append('## Tablas con diferencias')
        for t, d in diff['tables_changed'].items():
            lines.append(f'### {t}')
            if d['columns_only_local']:
                lines.append('- Columnas solo en LOCAL: ' + ', '.join(d['columns_only_local']))
            if d['columns_only_railway']:
                lines.append('- Columnas solo en RAILWAY: ' + ', '.join(d['columns_only_railway']))
            if d['columns_changed']:
                lines.append('- Columnas con cambios:')
                for ch in d['columns_changed']:
                    lines.append(f"  - {ch['column']}: {json.dumps(ch['changes'], ensure_ascii=False)}")
            lines.append('')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    logs_dir = os.path.join(ROOT, 'logs')
    local_path = os.path.join(logs_dir, 'schema_local.json')
    railway_path = os.path.join(logs_dir, 'schema_railway.json')

    if not (os.path.exists(local_path) and os.path.exists(railway_path)):
        print('❌ No se encontraron ambos archivos schema_local.json y schema_railway.json en logs/')
        sys.exit(1)

    local = load_schema(local_path)
    railway = load_schema(railway_path)
    diff = compare_schemas(local, railway)

    out_md = os.path.join(ROOT, 'docs', 'DB_SCHEMA_DIFF.md')
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    save_markdown(diff, out_md)

    out_json = os.path.join(ROOT, 'logs', 'schema_diff.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(diff, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f'Diff guardado en: {out_md} y {out_json}')


if __name__ == '__main__':
    main()
