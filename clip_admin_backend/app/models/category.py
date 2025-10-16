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

    def update_centroid_embedding(self, force_recalculate=False):
        """
        Recalcula y actualiza el centroide de embeddings para esta categoría
        Versión OPTIMIZADA que se ejecuta automáticamente cuando se procesan nuevas imágenes
        
        Args:
            force_recalculate (bool): Forzar recálculo aunque ya exista centroide
            
        Returns:
            bool: True si se calculó exitosamente, False si no
        """
        import json
        import numpy as np
        from datetime import datetime
        
        try:
            # Si ya existe centroide y no se fuerza recálculo, mantener existente
            if self.centroid_embedding and not force_recalculate:
                print(f"⚡ Centroide ya existe para {self.name}, usando existente")
                return True
            
            print(f"🔄 Calculando centroide para categoría {self.name}...")
            
            # Obtener todas las imágenes procesadas de esta categoría
            category_embeddings = []
            
            for product in self.products:
                for image in product.images:
                    if image.clip_embedding and image.is_processed:
                        try:
                            embedding_data = json.loads(image.clip_embedding)
                            embedding_array = np.array(embedding_data)
                            # Normalizar embedding individual
                            embedding_array = embedding_array / np.linalg.norm(embedding_array)
                            category_embeddings.append(embedding_array)
                        except Exception as e:
                            print(f"⚠️ Error procesando embedding de imagen {image.id}: {e}")
                            continue
            
            if not category_embeddings:
                print(f"❌ No hay embeddings válidos para {self.name}")
                self.centroid_embedding = None
                self.centroid_updated_at = None
                self.centroid_image_count = 0
                return False
            
            # Calcular centroide (promedio) y normalizar
            category_embeddings = np.array(category_embeddings)
            centroid = np.mean(category_embeddings, axis=0)
            centroid = centroid / np.linalg.norm(centroid)  # Normalizar centroide final
            
            # Guardar en BD como JSON
            self.centroid_embedding = json.dumps(centroid.tolist())
            self.centroid_updated_at = datetime.utcnow()
            self.centroid_image_count = len(category_embeddings)
            
            print(f"✅ Centroide actualizado para {self.name}: {len(category_embeddings)} imágenes")
            return True
            
        except Exception as e:
            print(f"❌ Error actualizando centroide para {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_centroid_embedding(self, auto_calculate=True):
        """
        Obtiene el centroide embedding desde BD (súper rápido)
        
        Args:
            auto_calculate (bool): Si calcular automáticamente si no existe
            
        Returns:
            np.array: Centroide embedding o None si no existe
        """
        import json
        import numpy as np
        
        # Si ya existe centroide en BD, devolverlo (súper rápido)
        if self.centroid_embedding:
            try:
                centroid_array = np.array(json.loads(self.centroid_embedding))
                print(f"⚡ Centroide cargado desde BD para {self.name} ({self.centroid_image_count} imágenes)")
                return centroid_array
            except Exception as e:
                print(f"⚠️ Error deserializando centroide para {self.name}: {e}")
                # Si hay error, limpiar centroide corrupto
                self.centroid_embedding = None
                self.centroid_updated_at = None
                self.centroid_image_count = 0
        
        # Si no existe y auto_calculate está habilitado, calcularlo
        if auto_calculate:
            print(f"🔄 Centroide no existe para {self.name}, calculando...")
            if self.update_centroid_embedding():
                # Commit inmediato para persistir en BD
                from .. import db
                try:
                    db.session.commit()
                    print(f"💾 Centroide guardado en BD para {self.name}")
                except Exception as e:
                    print(f"⚠️ Error guardando centroide en BD: {e}")
                    db.session.rollback()
                
                # Retornar centroide recién calculado
                if self.centroid_embedding:
                    return np.array(json.loads(self.centroid_embedding))
        
        print(f"❌ No se pudo obtener centroide para {self.name}")
        return None

    def needs_centroid_update(self):
        """
        Determina si el centroide necesita ser recalculado
        
        Returns:
            bool: True si necesita actualización
        """
        if not self.centroid_embedding:
            return True
        
        # Contar imágenes actuales con embeddings
        current_image_count = 0
        for product in self.products:
            for image in product.images:
                if image.clip_embedding and image.is_processed:
                    current_image_count += 1
        
        # Si el número de imágenes cambió, necesita actualización
        if current_image_count != self.centroid_image_count:
            print(f"🔄 {self.name}: {current_image_count} imágenes actuales vs {self.centroid_image_count} en centroide")
            return True
        
        return False

    @classmethod
    def recalculate_all_centroids(cls, client_id=None, force=False):
        """
        Recalcula centroides para todas las categorías
        
        Args:
            client_id (str): Solo recalcular para un cliente específico
            force (bool): Forzar recálculo aunque ya existan
            
        Returns:
            dict: Estadísticas del proceso
        """
        from .. import db
        
        query = cls.query.filter_by(is_active=True)
        if client_id:
            query = query.filter_by(client_id=client_id)
        
        categories = query.all()
        
        stats = {
            'total': len(categories),
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        print(f"🔄 Recalculando centroides para {len(categories)} categorías...")
        
        for category in categories:
            try:
                if force or category.needs_centroid_update():
                    if category.update_centroid_embedding(force_recalculate=force):
                        stats['updated'] += 1
                        print(f"✅ {category.name}: Actualizado")
                    else:
                        stats['errors'] += 1
                        print(f"❌ {category.name}: Error")
                else:
                    stats['skipped'] += 1
                    print(f"⏭️ {category.name}: No necesita actualización")
                    
            except Exception as e:
                stats['errors'] += 1
                print(f"❌ Error procesando {category.name}: {e}")
        
        # Commit todos los cambios
        try:
            db.session.commit()
            print(f"💾 Cambios guardados en BD")
        except Exception as e:
            print(f"❌ Error guardando en BD: {e}")
            db.session.rollback()
        
        print(f"📊 Estadísticas finales: {stats}")
        return stats
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
