"""
Script extendido para poblar la tabla `embeddings` con:
 - Categorías activas por cliente (type='category')
 - Colores base (type='color')
 - Vocabulario completo (colores, tipos, contextos) + variantes morfológicas (type='vocabulary')

Mejoras añadidas:
 - Argumentos: --target (local|railway), --client <uuid opcional>, --skip-* selectivos
 - Expansión morfológica básica (género y plural) para español: 'blanco'→'blanca', 'camisa'→'camisas'
 - Reutiliza caché persistente `client_vocabulary_cache` si existe
 - Evita recalcular embeddings si ya existen
"""
import sys
import os
import argparse
import json
import uuid
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../clip_admin_backend')))

from app import db
from app.models.category import Category
from app.models.product import Product
from app.models.embedding import Embedding
from app.models.client import Client
from app.utils.llm_query_normalizer import get_model, normalize_query
from dotenv import load_dotenv
from sqlalchemy import text

DEFAULT_RAILWAY_URI = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"


def ensure_env(target: str):
    """Configura la conexión DB según target para create_app() (usa DATABASE_URL)."""
    if target == 'railway':
        os.environ['DATABASE_URL'] = DEFAULT_RAILWAY_URI
        print(f"🌐 Target Railway: {DEFAULT_RAILWAY_URI}")
    else:
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env.local'))
        if not os.getenv('DATABASE_URL'):
            raise RuntimeError('DATABASE_URL no definido en .env.local')
        print(f"🖥️ Target Local (.env.local) {os.getenv('DATABASE_URL')}")
    os.environ['FLASK_ENV'] = 'development'


def expand_spanish_variants(term: str) -> set:
    """Genera variantes simples (género y plural) para términos en español."""
    variants = {term.lower()}
    t = term.lower()
    # Género o -> a
    if t.endswith('o') and len(t) > 3:
        variants.add(t[:-1] + 'a')
    # Género a -> o (menos común, pero útil para 'blanca'→'blanco')
    if t.endswith('a') and len(t) > 3:
        variants.add(t[:-1] + 'o')
    # Plural simple: añadir 's' si no termina en s
    if not t.endswith('s') and len(t) > 2:
        variants.add(t + 's')
    # Singular naive: quitar 's' final si >3
    if t.endswith('s') and len(t) > 3:
        variants.add(t[:-1])
    return variants


def batch_insert_embeddings(pairs, emb_type: str):
    """Inserta embeddings en lotes evitando duplicados previos."""
    added = 0
    for key, vector in pairs:
        exists = Embedding.query.filter_by(key=key, type=emb_type).first()
        if exists:
            continue
        db.session.add(Embedding(
            id=str(uuid.uuid4()),
            key=key,
            embedding=json.dumps([float(x) for x in vector]),
            type=emb_type
        ))
        added += 1
    if added:
        db.session.commit()
    return added


def populate_category_embeddings(client_filter=None):
    llm_model = get_model()
    pairs = []
    clients = Client.query.all() if not client_filter else Client.query.filter_by(id=client_filter).all()
    for client in clients:
        for category in Category.query.filter_by(client_id=client.id, is_active=True).all():
            key = f"category:{client.id}:{category.name.lower()}"
            emb = llm_model.encode(category.name.lower(), convert_to_tensor=False)
            pairs.append((key, emb))
    added = batch_insert_embeddings(pairs, 'category')
    print(f"📦 Categorías: {len(pairs)} procesadas, {added} nuevas")


def populate_color_embeddings():
    colores_base = [
        "blanco", "negro", "rojo", "azul", "verde", "amarillo", "gris", "marrón", "beige", "celeste", "naranja", "violeta", "rosa",
        "turquesa", "fucsia", "bordó", "dorado", "plateado", "marino", "caramelo"
    ]
    pairs = []
    for color in colores_base:
        key = f"color:{color.lower()}"
        result = normalize_query(color)
        emb = result.get('embedding')
        if emb:
            pairs.append((key, emb))
    added = batch_insert_embeddings(pairs, 'color')
    print(f"🎨 Colores base: {len(pairs)} procesados, {added} nuevos")


def _collect_client_vocabulary(client_id: str) -> dict:
    """Intenta leer vocabulario precalculado (client_vocabulary_cache); si falla usa extractor dinámico."""
    vocab = None
    try:
        row = db.session.execute(text("SELECT vocabulary FROM client_vocabulary_cache WHERE client_id=:cid"), {"cid": client_id}).fetchone()
        if row and row[0]:
            val = row[0]
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    val = None
            if isinstance(val, dict):
                vocab = {
                    'colores': list(val.get('colores', []) or []),
                    'tipos': list(val.get('tipos', []) or []),
                    'contextos': list(val.get('contextos', []) or [])
                }
    except Exception as e:
        print(f"⚠️ Error leyendo cache vocabulario cliente {client_id}: {e}")
    if not vocab:
        from app.utils.llm_query_normalizer import _extract_client_vocabulary
        raw = _extract_client_vocabulary(client_id)
        vocab = {
            'colores': raw.get('colores', []),
            'tipos': raw.get('tipos', []),
            'contextos': raw.get('contextos', [])
        }
    return vocab


def populate_vocabulary_embeddings(client_filter=None):
    llm_model = get_model()
    clients = Client.query.all() if not client_filter else Client.query.filter_by(id=client_filter).all()
    total_terms = 0
    total_new = 0
    for client in clients:
        vocab = _collect_client_vocabulary(str(client.id))
        # Paleta estándar adicional (evitar misses)
        paleta_estandar = [
            'negro', 'blanco', 'gris', 'azul', 'rojo', 'verde', 'amarillo',
            'naranja', 'rosa', 'violeta', 'morado', 'marrón', 'beige', 'celeste',
            'marino', 'turquesa', 'fucsia', 'bordó', 'dorado', 'plateado', 'caramelo'
        ]
        colores_full = list(set((vocab.get('colores') or []) + paleta_estandar))
        tipos_full = list(set(vocab.get('tipos') or []))
        contextos_full = list(set(vocab.get('contextos') or []))

        def expand_group(terms):
            expanded = set()
            for t in terms:
                for v in expand_spanish_variants(t):
                    expanded.add(v)
            return sorted(expanded)

        colores_exp = expand_group(colores_full)
        tipos_exp = expand_group(tipos_full)
        contextos_exp = expand_group(contextos_full)

        groups = {
            'colores': colores_exp,
            'tipos': tipos_exp,
            'contextos': contextos_exp
        }
        print(f"👤 Cliente {client.name}: colores={len(colores_exp)} tipos={len(tipos_exp)} contextos={len(contextos_exp)}")
        for group_name, terms in groups.items():
            pairs = []
            for term in terms:
                key = f"vocab:{term.lower()}"
                exists = Embedding.query.filter_by(key=key, type='vocabulary').first()
                if exists:
                    continue
                vec = llm_model.encode(term.lower(), convert_to_tensor=False)
                pairs.append((key, vec))
            added = batch_insert_embeddings(pairs, 'vocabulary')
            total_terms += len(terms)
            total_new += added
            print(f"  ▸ {group_name}: {len(terms)} términos, {added} nuevos")
    print(f"✅ Vocabulario total procesado: {total_terms} términos, nuevos insertados: {total_new}")


def _iter_color_values_from_attributes(attrs: dict):
    """Extrae valores de color desde attributes JSON (string | list | dict)."""
    if not attrs:
        return
    color_keys = {'color', 'colour', 'color_principal', 'color_secundario'}
    for k, v in (attrs or {}).items():
        if not k:
            continue
        if str(k).lower() not in color_keys:
            continue
        # Normalizar a lista de strings
        if v is None:
            continue
        if isinstance(v, str):
            yield v
        elif isinstance(v, list):
            for item in v:
                if item is not None:
                    yield str(item)
        elif isinstance(v, dict):
            val = v.get('value')
            if val is not None:
                yield str(val)


def _scan_catalog_and_populate_colors(client_filter=None):
    """Escanea productos y precomputa embeddings type='color' y también 'vocabulary' para términos de color encontrados."""
    llm_model = get_model()
    clients = Client.query.all() if not client_filter else Client.query.filter_by(id=client_filter).all()
    total_colors = 0
    total_new_colors = 0
    total_new_vocab = 0
    for client in clients:
        color_terms = set()
        products = Product.query.filter_by(client_id=client.id, is_active=True).all()
        for p in products:
            try:
                for val in _iter_color_values_from_attributes(p.attributes or {}):
                    t = (val or '').strip().lower()
                    if t:
                        color_terms.add(t)
            except Exception:
                continue
        if not color_terms:
            print(f"👤 Cliente {client.name}: sin colores detectados en catálogo")
            continue
        total_colors += len(color_terms)

        # 1) Embeddings type='color'
        color_pairs = []
        for term in sorted(color_terms):
            key = f"color:{term}"
            if not Embedding.query.filter_by(key=key, type='color').first():
                vec = llm_model.encode(term, convert_to_tensor=False)
                color_pairs.append((key, vec))
        total_new_colors += batch_insert_embeddings(color_pairs, 'color')

        # 2) También guardar como vocabulario (para evitar misses semánticos)
        vocab_pairs = []
        for term in sorted(color_terms):
            vkey = f"vocab:{term}"
            if not Embedding.query.filter_by(key=vkey, type='vocabulary').first():
                vec = llm_model.encode(term, convert_to_tensor=False)
                vocab_pairs.append((vkey, vec))
        total_new_vocab += batch_insert_embeddings(vocab_pairs, 'vocabulary')

        print(f"👤 Cliente {client.name}: colores únicos={len(color_terms)} nuevos(color)={len(color_pairs)} nuevos(vocab)={len(vocab_pairs)}")

    print(f"✅ Catálogo colores: términos totales detectados={total_colors} nuevos(color)={total_new_colors} nuevos(vocab)={total_new_vocab}")


def _scan_catalog_and_populate_tags(client_filter=None):
    """Escanea tags de productos y precomputa embeddings type='vocabulary' para cada tag distintivo."""
    llm_model = get_model()
    clients = Client.query.all() if not client_filter else Client.query.filter_by(id=client_filter).all()
    total_tags = 0
    total_new = 0
    for client in clients:
        tag_terms = set()
        products = Product.query.filter_by(client_id=client.id, is_active=True).all()
        for p in products:
            if not p.tags:
                continue
            # Split por coma y/o espacios; limpiar tokens cortos
            raw = p.tags.replace(';', ',')
            for part in raw.split(','):
                token = (part or '').strip().lower()
                if token and len(token) > 2:
                    tag_terms.add(token)
        if not tag_terms:
            print(f"👤 Cliente {client.name}: sin tags detectados en catálogo")
            continue
        total_tags += len(tag_terms)
        pairs = []
        for term in sorted(tag_terms):
            key = f"vocab:{term}"
            if not Embedding.query.filter_by(key=key, type='vocabulary').first():
                vec = llm_model.encode(term, convert_to_tensor=False)
                pairs.append((key, vec))
        total_new += batch_insert_embeddings(pairs, 'vocabulary')
        print(f"👤 Cliente {client.name}: tags únicos={len(tag_terms)} nuevos(vocab)={len(pairs)}")
    print(f"✅ Catálogo tags: términos totales detectados={total_tags} nuevos(vocab)={total_new}")


def parse_args():
    ap = argparse.ArgumentParser(description="Precomputar embeddings (categorías, colores, vocabulario)")
    ap.add_argument('--target', choices=['local', 'railway'], default='local', help='Destino de conexión DB')
    ap.add_argument('--client', help='ID de cliente (UUID) para limitar proceso')
    ap.add_argument('--skip-categories', action='store_true')
    ap.add_argument('--skip-colors', action='store_true')
    ap.add_argument('--skip-vocab', action='store_true')
    ap.add_argument('--scan-catalog-colors', action='store_true', help='Escanear catálogo (attributes.color*) y precomputar type=color y vocabulario para esos términos')
    ap.add_argument('--scan-catalog-tags', action='store_true', help='Escanear tags de productos y precomputar vocabulario de tags')
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ensure_env(args.target)
    from app import create_app
    app = create_app()
    with app.app_context():
        start_all = datetime.utcnow()
        print(f"🚀 Inicio precálculo embeddings ({start_all.isoformat()})")
        if not args.skip_categories:
            print("🔄 Generando embeddings de categorías...")
            populate_category_embeddings(client_filter=args.client)
        if not args.skip_colors:
            print("🔄 Generando embeddings de colores base...")
            populate_color_embeddings()
        if not args.skip_vocab:
            print("🔄 Generando embeddings de vocabulario (colores/tipos/contextos + variantes)...")
            populate_vocabulary_embeddings(client_filter=args.client)
        if args.scan_catalog_colors:
            print("🔍 Escaneando catálogo para colores reales de productos...")
            _scan_catalog_and_populate_colors(client_filter=args.client)
        if args.scan_catalog_tags:
            print("🔍 Escaneando catálogo para tags de productos...")
            _scan_catalog_and_populate_tags(client_filter=args.client)
        print(f"✅ Proceso completado en {(datetime.utcnow()-start_all).total_seconds():.2f}s")
