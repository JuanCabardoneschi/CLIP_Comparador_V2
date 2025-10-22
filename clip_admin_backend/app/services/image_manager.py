"""
Servicio centralizado para manejo de imágenes
Unifica toda la lógica de almacenamiento, recuperación y manipulación de imágenes
"""

import os
import uuid
import base64
import warnings
from typing import Optional, List, Tuple
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import current_app
from PIL import Image as PILImage
from app.models.image import Image


class ImageManager:
    """
    Clase centralizada para el manejo de imágenes
    Encapsula toda la lógica de almacenamiento local
    """

    def __init__(self):
        self.base_upload_path = "static/uploads/clients"
        self.allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        self.max_file_size = 15 * 1024 * 1024  # 15MB

    def _get_client_slug(self, image: Image) -> str:
        """
        Obtiene el slug del cliente dinámicamente desde la base de datos

        Args:
            image: Objeto Image

        Returns:
            Slug del cliente o fallback seguro
        """
        try:
            if hasattr(image, 'client_slug'):
                return image.client_slug

            from app.models.client import Client
            client = Client.query.get(image.client_id)
            return client.slug if client else "demo_fashion_store"
        except Exception:
            return "demo_fashion_store"  # Fallback seguro

    def _get_upload_directory(self, client_slug: str = "demo_fashion_store") -> str:
        """
        Obtiene el directorio de subida para un cliente
        """
        upload_dir = os.path.join(
            current_app.root_path,
            self.base_upload_path,
            client_slug
        )
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    def _get_relative_path(self, client_slug: str = "demo_fashion_store") -> str:
        """
        Obtiene la ruta relativa para URLs
        """
        return f"/{self.base_upload_path}/{client_slug}/"

    def _is_allowed_file(self, filename: str) -> bool:
        """
        Verifica si el archivo tiene una extensión permitida
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def _generate_unique_filename(self, original_filename: str) -> str:
        """
        Genera un nombre único para el archivo
        """
        secured_name = secure_filename(original_filename)
        return f"{uuid.uuid4()}_{secured_name}"

    def _get_image_dimensions(self, file_path: str) -> Tuple[int, int]:
        """
        Obtiene las dimensiones de una imagen
        """
        try:
            with PILImage.open(file_path) as img:
                return img.size
        except Exception:
            return (0, 0)

    def upload_image(self,
                    file: FileStorage,
                    product_id: int,
                    client_id: int = 1,
                    client_slug: str = None,
                    alt_text: str = "",
                    display_order: int = 0,
                    is_primary: bool = False) -> Optional[Image]:
        """
        Sube una imagen y crea el registro en base de datos

        Args:
            file: Archivo de imagen a subir
            product_id: ID del producto
            client_id: ID del cliente
            client_slug: Slug del cliente (auto-detectado si no se proporciona)
            alt_text: Texto alternativo
            display_order: Orden de visualización
            is_primary: Si es imagen principal

        Returns:
            Objeto Image creado o None si hay error
        """
        # Auto-detectar client_slug si no se proporciona
        if client_slug is None:
            try:
                from app.models.client import Client
                client = Client.query.get(client_id)
                client_slug = client.slug if client else "demo_fashion_store"
            except Exception:
                client_slug = "demo_fashion_store"
        if not file or not file.filename:
            return None

        if not self._is_allowed_file(file.filename):
            raise ValueError(f"Tipo de archivo no permitido. Permitidos: {', '.join(self.allowed_extensions)}")

        # Verificar tamaño del archivo
        file.seek(0, 2)  # Ir al final del archivo
        file_size = file.tell()
        file.seek(0)  # Volver al inicio

        if file_size > self.max_file_size:
            raise ValueError(f"Archivo demasiado grande. Máximo: {self.max_file_size / (1024*1024)}MB")

        try:
            # Generar nombre único
            unique_filename = self._generate_unique_filename(file.filename)

            # Obtener directorio de subida
            upload_dir = self._get_upload_directory(client_slug)

            # Guardar archivo temporalmente
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)

            # Obtener dimensiones
            width, height = self._get_image_dimensions(file_path)

            # 🌐 SUBIR A CLOUDINARY Y GENERAR BASE64
            cloudinary_url = None
            cloudinary_public_id = None
            base64_data = None

            try:
                import cloudinary
                import cloudinary.uploader

                # Configurar Cloudinary si no está configurado
                if not cloudinary.config().cloud_name:
                    cloudinary.config(
                        cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME', 'dgtsan81n'),
                        api_key=current_app.config.get('CLOUDINARY_API_KEY'),
                        api_secret=current_app.config.get('CLOUDINARY_API_SECRET')
                    )

                # Generar public_id único para Cloudinary
                public_id = f"{client_slug}/products/{product_id}/{unique_filename.split('.')[0]}"

                # Subir a Cloudinary directamente
                cloudinary_result = cloudinary.uploader.upload(
                    file_path,
                    public_id=public_id,
                    folder=f"{client_slug}/products",
                    resource_type="image",
                    overwrite=True
                )

                if cloudinary_result:
                    cloudinary_url = cloudinary_result.get('secure_url')
                    cloudinary_public_id = cloudinary_result.get('public_id')

                    # Generar base64 desde archivo local
                    import base64
                    with open(file_path, "rb") as img_file:
                        img_data = img_file.read()
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        mime_type = file.mimetype or "image/jpeg"
                        base64_data = f"data:{mime_type};base64,{img_base64}"

                    print(f"✅ Imagen subida a Cloudinary: {cloudinary_url}")
                else:
                    print("⚠️ Error subiendo a Cloudinary, manteniendo archivo local")

            except Exception as e:
                print(f"⚠️ Error en Cloudinary: {e}, manteniendo archivo local")

            # Crear registro en base de datos con datos de Cloudinary
            from app import db
            image = Image(
                product_id=product_id,
                client_id=client_id,
                filename=unique_filename,
                original_filename=file.filename,
                cloudinary_url=cloudinary_url,
                cloudinary_public_id=cloudinary_public_id,
                base64_data=base64_data,
                file_size=file_size,
                width=width,
                height=height,
                mime_type=file.mimetype,
                alt_text=alt_text,
                display_order=display_order,
                is_primary=is_primary
            )

            # 🗑️ LIMPIAR ARCHIVO LOCAL (ya está en Cloudinary)
            if cloudinary_url and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"🗑️ Archivo local eliminado: {file_path}")
                except Exception as e:
                    print(f"⚠️ No se pudo eliminar archivo local: {e}")

            db.session.add(image)
            return image

        except Exception as e:
            # Limpiar archivo si se creó
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            raise e

    def delete_image(self, image: Image, client_slug: str = None) -> bool:
        """
        Elimina una imagen del sistema de archivos y base de datos

        Args:
            image: Objeto Image a eliminar
            client_slug: Slug del cliente (auto-detectado si no se proporciona)

        Returns:
            True si se eliminó correctamente
        """
        if client_slug is None:
            client_slug = self._get_client_slug(image)

        try:
            # Eliminar archivo físico
            if image.filename:
                file_path = os.path.join(
                    self._get_upload_directory(client_slug),
                    image.filename
                )
                if os.path.exists(file_path):
                    os.remove(file_path)

            # Eliminar de base de datos
            from app import db
            db.session.delete(image)
            return True

        except Exception:
            return False

    def get_image_url(self, image: Image, client_slug: str = None) -> str:
        """
        ⚠️ DEPRECATED: Usar image.display_url directamente

        Obtiene la URL pública de una imagen - SOLO Cloudinary

        Args:
            image: Objeto Image
            client_slug: Slug del cliente (auto-detectado si no se proporciona)

        Returns:
            URL de la imagen (Cloudinary o placeholder)

        Deprecated:
            Usar `image.display_url` directamente en lugar de este método.
            Este método será eliminado en versiones futuras.
        """
        warnings.warn(
            "ImageManager.get_image_url() está deprecado. "
            "Usar image.display_url directamente. "
            "Este método será eliminado en futuras versiones.",
            DeprecationWarning,
            stacklevel=2
        )
        # SOLO usar Cloudinary - no hay fallback local
        if image.cloudinary_url:
            return image.cloudinary_url
        return '/static/images/placeholder.svg'

    def get_image_path(self, image: Image, client_slug: str = None) -> str:
        """
        Obtiene la ruta completa del archivo de imagen

        Args:
            image: Objeto Image
            client_slug: Slug del cliente (auto-detectado si no se proporciona)

        Returns:
            Ruta completa del archivo
        """
        if client_slug is None:
            client_slug = self._get_client_slug(image)

        return os.path.join(
            self._get_upload_directory(client_slug),
            image.filename
        )

    def image_exists(self, image: Image, client_slug: str = None) -> bool:
        """
        Verifica si el archivo de imagen existe físicamente

        Args:
            image: Objeto Image
            client_slug: Slug del cliente (auto-detectado si no se proporciona)

        Returns:
            True si el archivo existe
        """
        if client_slug is None:
            client_slug = self._get_client_slug(image)

        file_path = self.get_image_path(image, client_slug)
        return os.path.exists(file_path)

    def get_image_base64(self, image: Image, client_slug: str = None) -> Optional[str]:
        """
        Obtiene imagen en base64 - OPTIMIZADO: lee directamente de BD

        Args:
            image: Objeto Image
            client_slug: Slug del cliente (no necesario, mantenido por compatibilidad)

        Returns:
            String base64 de la imagen o None si no existe
        """
        try:
            # 🚀 PRIORIDAD 1: Leer base64 directamente desde BD (súper rápido)
            if image.base64_data:
                return image.base64_data

            # 🌐 FALLBACK: Si no hay base64 en BD, generar desde Cloudinary
            if image.cloudinary_url:
                import requests
                response = requests.get(image.cloudinary_url, timeout=30)
                response.raise_for_status()

                img_data = response.content
                img_base64 = base64.b64encode(img_data).decode('utf-8')

                # Determinar el tipo MIME
                mime_type = image.mime_type or "image/jpeg"
                base64_data = f"data:{mime_type};base64,{img_base64}"

                # Guardar en BD para futuras consultas
                image.base64_data = base64_data
                db.session.commit()

                return base64_data

            # 📁 ÚLTIMO FALLBACK: Archivo local (obsoleto pero por compatibilidad)
            if client_slug is None:
                client_slug = self._get_client_slug(image)

            file_path = self.get_image_path(image, client_slug)
            if not os.path.exists(file_path):
                return None

            with open(file_path, "rb") as img_file:
                img_data = img_file.read()
                img_base64 = base64.b64encode(img_data).decode('utf-8')

                # Determinar el tipo MIME
                mime_type = image.mime_type or "image/jpeg"
                return f"data:{mime_type};base64,{img_base64}"

        except Exception:
            return None

    def get_images_by_product(self, product_id: int) -> List[Image]:
        """
        Obtiene todas las imágenes de un producto

        Args:
            product_id: ID del producto

        Returns:
            Lista de objetos Image
        """
        return Image.query.filter_by(product_id=product_id).order_by(
            Image.display_order, Image.created_at
        ).all()

    def get_primary_image(self, product_id: int) -> Optional[Image]:
        """
        Obtiene la imagen principal de un producto

        Args:
            product_id: ID del producto

        Returns:
            Imagen principal o la primera imagen disponible
        """
        # Buscar imagen marcada como principal
        primary = Image.query.filter_by(
            product_id=product_id,
            is_primary=True
        ).first()

        if primary:
            return primary

        # Si no hay principal, devolver la primera
        return Image.query.filter_by(product_id=product_id).order_by(
            Image.display_order, Image.created_at
        ).first()

    def set_primary_image(self, image_id: int, product_id: int) -> bool:
        """
        Establece una imagen como principal para un producto

        Args:
            image_id: ID de la imagen a marcar como principal
            product_id: ID del producto

        Returns:
            True si se actualizó correctamente
        """
        try:
            from app import db

            # Desmarcar todas las imágenes del producto como principales
            Image.query.filter_by(
                product_id=product_id,
                is_primary=True
            ).update({"is_primary": False})

            # Marcar la nueva imagen como principal
            image = Image.query.get(image_id)
            if image and image.product_id == product_id:
                image.is_primary = True
                db.session.commit()
                return True

            return False

        except Exception:
            return False

    def cleanup_orphaned_files(self, client_slug: str = "demo_fashion_store") -> int:
        """
        Limpia archivos huérfanos (archivos sin registro en BD)

        Args:
            client_slug: Slug del cliente

        Returns:
            Número de archivos eliminados
        """
        upload_dir = self._get_upload_directory(client_slug)
        if not os.path.exists(upload_dir):
            return 0

        # Obtener todos los filenames registrados en BD
        registered_files = set(
            img.filename for img in Image.query.filter_by(client_id=1).all()
            if img.filename
        )

        # Encontrar archivos huérfanos
        orphaned_count = 0
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            if os.path.isfile(file_path) and filename not in registered_files:
                try:
                    os.remove(file_path)
                    orphaned_count += 1
                except:
                    pass

        return orphaned_count


# Instancia global del manejador de imágenes
image_manager = ImageManager()
