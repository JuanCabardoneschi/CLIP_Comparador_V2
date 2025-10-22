"""
Cloudinary Image Manager
Servicio para gestión de imágenes en Cloudinary
"""
import os
import uuid
import warnings
import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Optional, Dict, Any, Tuple
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import current_app


class CloudinaryImageManager:
    """Manager para subida y gestión de imágenes en Cloudinary"""

    def __init__(self):
        self.allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}
        self.max_file_size = 15 * 1024 * 1024  # 15MB
        self._configure_cloudinary()

    def _configure_cloudinary(self):
        """Configurar Cloudinary con variables de entorno"""
        try:
            cloudinary.config(
                cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
                api_key=os.getenv("CLOUDINARY_API_KEY"),
                api_secret=os.getenv("CLOUDINARY_API_SECRET"),
                secure=True
            )
            print(f"✅ Cloudinary configurado para: {os.getenv('CLOUDINARY_CLOUD_NAME', 'N/A')}")
        except Exception as e:
            print(f"❌ Error configurando Cloudinary: {e}")

    def _is_allowed_file(self, filename: str) -> bool:
        """Verificar si el archivo tiene una extensión permitida"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def _generate_public_id(self, client_slug: str, product_id: str, filename: str) -> str:
        """Generar ID público único para Cloudinary"""
        secured_name = secure_filename(filename)
        name_without_ext = os.path.splitext(secured_name)[0]
        unique_id = str(uuid.uuid4())[:8]
        # Solo retornar el path relativo dentro de la carpeta del producto
        return f"products/{product_id}/{name_without_ext}_{unique_id}"

    def upload_image(self,
                    file: FileStorage,
                    product_id: str,
                    client_id: str,
                    client_slug: str = None,
                    is_primary: bool = False,
                    alt_text: str = None) -> Optional['Image']:
        """
        Subir imagen a Cloudinary y crear registro en base de datos

        Args:
            file: Archivo de imagen
            product_id: ID del producto
            client_id: ID del cliente
            client_slug: Slug del cliente
            is_primary: Si es imagen principal
            alt_text: Texto alternativo

        Returns:
            Objeto Image creado o None si hay error
        """
        if not file or not file.filename:
            return None

        if not self._is_allowed_file(file.filename):
            raise ValueError(f"Tipo de archivo no permitido. Permitidos: {', '.join(self.allowed_extensions)}")

        # Auto-detectar client_slug si no se proporciona
        if client_slug is None:
            try:
                from app.models.client import Client
                client = Client.query.get(client_id)
                client_slug = client.slug if client else "demo_fashion_store"
            except Exception:
                client_slug = "demo_fashion_store"

        # Verificar tamaño del archivo
        file.seek(0, 2)  # Ir al final
        file_size = file.tell()
        file.seek(0)  # Volver al inicio

        if file_size > self.max_file_size:
            raise ValueError(f"Archivo demasiado grande. Máximo: {self.max_file_size / (1024*1024):.1f}MB")

        try:
            # Generar public_id único
            public_id = self._generate_public_id(client_slug, product_id, file.filename)

            # Subir a Cloudinary
            upload_result = cloudinary.uploader.upload(
                file,
                public_id=public_id,
                folder=f"clip_v2/{client_slug}",
                resource_type="image",
                format="auto",  # Auto-optimización de formato
                quality="auto",  # Calidad automática
                fetch_format="auto",  # WebP cuando sea compatible
                transformation=[
                    {"quality": "auto:good"},
                    {"fetch_format": "auto"}
                ],
                eager=[
                    {"width": 300, "height": 300, "crop": "fill"},  # Thumbnail
                    {"width": 800, "height": 600, "crop": "limit"}   # Medium
                ]
            )

            print(f"✅ Imagen subida a Cloudinary: {upload_result['secure_url']}")

            # Crear registro en base de datos
            from app import db
            from app.models.image import Image

            image = Image(
                client_id=client_id,
                product_id=product_id,
                filename=secure_filename(file.filename),
                original_filename=file.filename,
                cloudinary_url=upload_result['secure_url'],
                cloudinary_public_id=upload_result['public_id'],
                width=upload_result.get('width'),
                height=upload_result.get('height'),
                file_size=upload_result.get('bytes', file_size),
                mime_type=f"image/{upload_result.get('format', 'jpeg')}",
                alt_text=alt_text or f"Imagen de {product_id}",
                is_primary=is_primary,
                # Al subir una imagen NO está procesada para embeddings aún
                is_processed=False,
                upload_status="pending"
            )

            db.session.add(image)
            db.session.commit()

            print(f"✅ Registro creado en BD: Image ID {image.id}")
            return image

        except Exception as e:
            print(f"❌ Error subiendo imagen: {e}")
            raise ValueError(f"Error subiendo a Cloudinary: {str(e)}")

    def upload_local_file(self,
                         local_path: str,
                         product_id: str,
                         client_id: str,
                         client_slug: str,
                         is_primary: bool = False) -> Optional['Image']:
        """
        Subir archivo local existente a Cloudinary

        Args:
            local_path: Ruta del archivo local
            product_id: ID del producto
            client_id: ID del cliente
            client_slug: Slug del cliente
            is_primary: Si es imagen principal

        Returns:
            Objeto Image creado o None si hay error
        """
        if not os.path.exists(local_path):
            print(f"❌ Archivo no encontrado: {local_path}")
            return None

        filename = os.path.basename(local_path)

        if not self._is_allowed_file(filename):
            print(f"❌ Tipo de archivo no permitido: {filename}")
            return None

        try:
            # Generar public_id único
            public_id = self._generate_public_id(client_slug, product_id, filename)

            # Subir a Cloudinary
            upload_result = cloudinary.uploader.upload(
                local_path,
                public_id=public_id,
                folder=f"clip_v2/{client_slug}",
                resource_type="image",
                format="auto",
                quality="auto",
                fetch_format="auto",
                transformation=[
                    {"quality": "auto:good"},
                    {"fetch_format": "auto"}
                ]
            )

            print(f"✅ Archivo local subido: {local_path} → {upload_result['secure_url']}")

            # Crear registro en BD
            from app import db
            from app.models.image import Image

            image = Image(
                client_id=client_id,
                product_id=product_id,
                filename=filename,
                original_filename=filename,
                cloudinary_url=upload_result['secure_url'],
                cloudinary_public_id=upload_result['public_id'],
                width=upload_result.get('width'),
                height=upload_result.get('height'),
                file_size=upload_result.get('bytes'),
                mime_type=f"image/{upload_result.get('format', 'jpeg')}",
                alt_text=f"Imagen de {product_id}",
                is_primary=is_primary,
                # Al subir una imagen NO está procesada para embeddings aún
                is_processed=False,
                upload_status="pending"
            )

            db.session.add(image)
            db.session.commit()

            return image

        except Exception as e:
            print(f"❌ Error subiendo archivo local {local_path}: {e}")
            return None

    def delete_image(self, image: 'Image') -> bool:
        """
        Eliminar imagen de Cloudinary y base de datos

        Args:
            image: Objeto Image a eliminar

        Returns:
            True si se eliminó correctamente
        """
        try:
            # Eliminar de Cloudinary
            if image.cloudinary_public_id:
                result = cloudinary.uploader.destroy(image.cloudinary_public_id)
                print(f"✅ Imagen eliminada de Cloudinary: {image.cloudinary_public_id}")

            # Eliminar de base de datos
            from app import db
            db.session.delete(image)
            db.session.commit()

            print(f"✅ Registro eliminado de BD: {image.filename}")
            return True

        except Exception as e:
            print(f"❌ Error eliminando imagen: {e}")
            return False

    def get_image_url(self, image: 'Image', transformation: Dict[str, Any] = None) -> Optional[str]:
        """
        ⚠️ DEPRECATED: Usar image.display_url directamente

        Obtener URL de imagen con transformaciones opcionales

        Args:
            image: Objeto Image
            transformation: Diccionario con transformaciones de Cloudinary

        Returns:
            URL de la imagen

        Deprecated:
            Usar `image.display_url` directamente en lugar de este método.
            Este método será eliminado en versiones futuras.
        """
        warnings.warn(
            "CloudinaryImageManager.get_image_url() está deprecado. "
            "Usar image.display_url directamente. "
            "Este método será eliminado en futuras versiones.",
            DeprecationWarning,
            stacklevel=2
        )
        if not image.cloudinary_url and not image.cloudinary_public_id:
            return None

        if transformation and image.cloudinary_public_id:
            # Generar URL con transformaciones
            return cloudinary.CloudinaryImage(image.cloudinary_public_id).build_url(**transformation)

        return image.cloudinary_url

    def get_image_base64(self, image: 'Image') -> Optional[str]:
        """
        ⚠️ DEPRECATED: Cloudinary devuelve URLs, no base64

        Obtener imagen como base64 (para compatibilidad con el código existente)

        Args:
            image: Objeto Image

        Returns:
            URL de Cloudinary (ya optimizada)

        Deprecated:
            Este método está deprecado. Cloudinary maneja URLs directamente.
            Usar `image.display_url` en su lugar.
        """
        warnings.warn(
            "CloudinaryImageManager.get_image_base64() está deprecado. "
            "Usar image.display_url directamente.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.get_image_url(image)

    def test_connection(self) -> bool:
        """
        Probar la conexión con Cloudinary

        Returns:
            True si la conexión es exitosa
        """
        try:
            # Probar conexión obteniendo información de la cuenta
            result = cloudinary.api.ping()
            print(f"✅ Conexión Cloudinary exitosa: {result}")
            return True
        except Exception as e:
            print(f"❌ Error conectando con Cloudinary: {e}")
            return False


# Instancia global
cloudinary_manager = CloudinaryImageManager()
