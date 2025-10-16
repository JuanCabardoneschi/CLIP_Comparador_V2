"""
Modelo Category para CLIP Comparador V2
"""
from datetime import datetime
from .. import db

class Category(db.Model):
    """Modelo para categorías de productos con soporte bilingüe para CLIP"""
    __tablename__ = 'categories'

    id = db.Column(db.String(36), primary_key=True)
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)

    # Campos bilingües
    name = db.Column(db.String(100), nullable=False)  # Nombre en español (interfaz)
    name_en = db.Column(db.String(100), nullable=False)  # Nombre en inglés (CLIP)
    alternative_terms = db.Column(db.Text)  # Términos alternativos separados por coma
    description = db.Column(db.Text)

    # Campos específicos para CLIP
    clip_prompt = db.Column(db.Text)  # Prompt optimizado para CLIP en inglés
    visual_features = db.Column(db.Text)  # JSON con características visuales clave
    confidence_threshold = db.Column(db.Float, default=0.75)  # Umbral de confianza
    centroid_embedding = db.Column(db.Text)  # Embedding centroide precalculado de la categoría
    centroid_updated_at = db.Column(db.DateTime)  # Última actualización del centroide

    # Campos de interfaz
    color = db.Column(db.String(7), default='#007bff')  # Color hex para la UI
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    client = db.relationship('Client', backref='categories')
    products = db.relationship('Product', backref='category', lazy='dynamic')

    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            import uuid
            kwargs['id'] = str(uuid.uuid4())
        super(Category, self).__init__(**kwargs)

    def __repr__(self):
        return f'<Category {self.name}>'

    def update_centroid_embedding(self):
        """
        Recalcula y actualiza el centroide de embeddings para esta categoría
        Se llama automáticamente cuando se procesan nuevas imágenes
        """
        import json
        import numpy as np
        from datetime import datetime
        
        try:
            # Obtener todas las imágenes procesadas de esta categoría
            category_embeddings = []
            
            for product in self.products:
                for image in product.images:
                    if image.clip_embedding and image.is_processed:
                        try:
                            embedding_data = json.loads(image.clip_embedding)
                            embedding_array = np.array(embedding_data)
                            # Normalizar embedding
                            embedding_array = embedding_array / np.linalg.norm(embedding_array)
                            category_embeddings.append(embedding_array)
                        except Exception:
                            continue
            
            if not category_embeddings:
                self.centroid_embedding = None
                self.centroid_updated_at = None
                return False
            
            # Calcular centroide (promedio) y normalizar
            category_embeddings = np.array(category_embeddings)
            centroid = np.mean(category_embeddings, axis=0)
            centroid = centroid / np.linalg.norm(centroid)
            
            # Guardar en BD como JSON
            self.centroid_embedding = json.dumps(centroid.tolist())
            self.centroid_updated_at = datetime.utcnow()
            
            print(f"🔄 Centroide actualizado para categoría {self.name}: {len(category_embeddings)} imágenes")
            return True
            
        except Exception as e:
            print(f"❌ Error actualizando centroide para {self.name}: {e}")
            return False

    def get_centroid_embedding(self):
        """
        Obtiene el centroide embedding, recalculándolo si es necesario
        """
        import json
        import numpy as np
        
        if not self.centroid_embedding:
            if self.update_centroid_embedding():
                # Guardar cambios en BD
                from .. import db
                db.session.commit()
        
        if self.centroid_embedding:
            try:
                return np.array(json.loads(self.centroid_embedding))
            except Exception:
                return None
        
        return None
        """Convierte el objeto a diccionario para JSON"""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'name': self.name,
            'name_en': self.name_en,
            'alternative_terms': self.alternative_terms,
            'description': self.description,
            'clip_prompt': self.clip_prompt,
            'visual_features': self.visual_features,
            'confidence_threshold': self.confidence_threshold,
            'color': self.color,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'product_count': self.products.count()
        }

    @staticmethod
    def auto_translate_to_english(spanish_name, client_industry='general'):
        """Traducción automática contextual basada en el rubro del cliente"""
        try:
            # Intentar traducción automática real
            from googletrans import Translator

            translator = Translator()

            # Normalizar entrada
            name_clean = spanish_name.strip()

            # Traducir al inglés
            result = translator.translate(name_clean, src='es', dest='en')
            english_name = result.text.lower().strip()

            # Post-procesamiento basado en industria del cliente
            english_name = Category._post_process_translation(english_name, spanish_name, client_industry)

            print(f"🔄 Traducción automática ({client_industry}): '{spanish_name}' → '{english_name}'")
            return english_name

        except ImportError:
            print("⚠️  googletrans no instalado, usando traducción simple")
            # Fallback sin librería externa
            return Category._simple_translate(spanish_name)
        except Exception as e:
            print(f"❌ Error en traducción automática: {e}")
            # Fallback en caso de error
            return Category._simple_translate(spanish_name)

    @staticmethod
    def _post_process_translation(english_name, original_spanish, client_industry='general'):
        """Post-procesar traducción basado en el rubro del cliente"""
        original_upper = original_spanish.upper().strip()

        # Correcciones generales (espacios, etc.)
        general_corrections = {
            't -shirts': 't-shirts',
            'lady shirts': 'women shirts',
            'lady vest': 'women vest',
            'lady shoe': 'women shoes'
        }

        # Aplicar correcciones generales
        if english_name in general_corrections:
            english_name = general_corrections[english_name]

        # Correcciones específicas por industria
        if client_industry == 'medical' or client_industry == 'healthcare':
            medical_corrections = {
                'both dress man': 'medical scrubs men',
                'both dress lady': 'medical scrubs women',
                'casacas': 'lab coats'
            }

            if english_name in medical_corrections:
                return medical_corrections[english_name]

            # Correcciones por palabra clave para contexto médico
            if 'AMBO' in original_upper:
                if 'HOMBRE' in original_upper:
                    return 'medical scrubs men'
                elif 'DAMA' in original_upper:
                    return 'medical scrubs women'

            if 'CASACAS' in original_upper:
                return 'lab coats'

        elif client_industry == 'fashion' or client_industry == 'clothing':
            fashion_corrections = {
                'divers': 'sweatshirts',
                'casacas': 'jackets'
            }

            if english_name in fashion_corrections:
                return fashion_corrections[english_name]

            if 'BUZOS' in original_upper:
                return 'sweatshirts'

        elif client_industry == 'sports':
            sports_corrections = {
                'divers': 'sportswear',
                'buzos': 'athletic wear'
            }

            if english_name in sports_corrections:
                return sports_corrections[english_name]

        return english_name

    @staticmethod
    def _simple_translate(spanish_name):
        """Traducción simple sin servicios externos (fallback)"""
        # Limpieza básica para CLIP
        name_clean = spanish_name.lower().strip()

        # Reemplazos básicos comunes
        replacements = {
            'hombre': 'men',
            'dama': 'women',
            'vestir': 'formal',
            'ñ': 'n'
        }

        for spanish, english in replacements.items():
            name_clean = name_clean.replace(spanish, english)

        return name_clean

    @staticmethod
    def generate_clip_prompt(name_en, visual_features=None, alternative_terms=None):
        """Genera prompt optimizado para CLIP basado en la categoría"""
        # Construir términos básicos
        terms = [name_en]

        # Agregar términos alternativos si existen
        if alternative_terms:
            alt_terms = [term.strip() for term in alternative_terms.split(',') if term.strip()]
            terms.extend(alt_terms[:3])  # Limitar a 3 términos alternativos para evitar prompts muy largos

        # Crear el prompt base con términos principales
        main_terms = ', '.join(terms[:2])  # Usar máximo 2 términos principales
        base_prompt = f"a photo of {main_terms}"

        if visual_features:
            # Si hay características específicas, agregarlas
            features = visual_features.replace(',', ' and')
            return f"a photo of {main_terms} showing {features}"

        return base_prompt

    @staticmethod
    def get_by_client(client_id, active_only=True):
        """Obtiene categorías por cliente"""
        query = Category.query.filter_by(client_id=client_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Category.name).all()

    @staticmethod
    def get_top_categories(client_id, limit=5):
        """Obtiene las categorías con más productos"""
        from app.models.product import Product
        return db.session.query(Category, db.func.count(Product.id).label('product_count'))\
            .join(Product, Category.id == Product.category_id, isouter=True)\
            .filter(Category.client_id == client_id, Category.is_active == True)\
            .group_by(Category.id)\
            .order_by(db.func.count(Product.id).desc())\
            .limit(limit).all()
