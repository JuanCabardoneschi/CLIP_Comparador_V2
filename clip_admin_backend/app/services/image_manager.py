"""
Servicio centralizado para manejo de imágenes
Unifica toda la lógica de almacenamiento, recuperación y manipulación de imágenes
"""

import os
import uuid
import base64
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

            # Guardar archivo
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)

            # Obtener dimensiones
            width, height = self._get_image_dimensions(file_path)

            # Crear registro en base de datos
            from app import db
            image = Image(
                product_id=product_id,
                client_id=client_id,
                filename=unique_filename,
                original_filename=file.filename,
                file_size=file_size,
                width=width,
                height=height,
                mime_type=file.mimetype,
                alt_text=alt_text,
                display_order=display_order,
                is_primary=is_primary
            )

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
        Obtiene la URL pública de una imagen

        Args:
            image: Objeto Image
            client_slug: Slug del cliente (auto-detectado si no se proporciona)

        Returns:
            URL de la imagen
        """
        if client_slug is None:
            client_slug = self._get_client_slug(image)

        return f"{self._get_relative_path(client_slug)}{image.filename}"

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
        Convierte una imagen a base64 para el API

        Args:
            image: Objeto Image
            client_slug: Slug del cliente (auto-detectado si no se proporciona)

        Returns:
            String base64 de la imagen o None si no existe
        """
        if client_slug is None:
            client_slug = self._get_client_slug(image)

        try:
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
