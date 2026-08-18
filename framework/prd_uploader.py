"""PRD file upload and processing module."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader

from framework.models import PRDDocument

logger = logging.getLogger(__name__)


class PRDUploadError(Exception):
    """Custom exception for PRD upload errors."""

    pass


class PRDUploader:
    """Handle PRD file uploads and validation."""

    SUPPORTED_FORMATS = [".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"]
    MAX_FILE_SIZE_MB = 50

    def __init__(self, storage_dir: Path = Path("prd")):
        """Initialize PRD uploader.

        Args:
            storage_dir: Directory to store uploaded PRD files.
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PRD storage directory: {self.storage_dir}")

    def validate_file(self, file_path: Path) -> bool:
        """Validate uploaded file format and size.

        Args:
            file_path: Path to the file to validate.

        Returns:
            True if file is valid.

        Raises:
            PRDUploadError: If file is invalid.
        """
        if not file_path.exists():
            raise PRDUploadError(f"File not found: {file_path}")

        # Check format
        if not self._is_supported_format(file_path):
            raise PRDUploadError(
                f"Unsupported format: {file_path.suffix}. "
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        # Check size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.MAX_FILE_SIZE_MB:
            raise PRDUploadError(
                f"File too large: {file_size_mb:.2f}MB. "
                f"Max size: {self.MAX_FILE_SIZE_MB}MB"
            )

        logger.info(f"File validation passed: {file_path.name} ({file_size_mb:.2f}MB)")
        return True

    def _is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported.

        Args:
            file_path: Path to the file.

        Returns:
            True if format is supported.
        """
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS

    def process_image(self, image_path: Path, max_dimension: int = 1920) -> Path:
        """Process and optimize image for LLM analysis.

        Args:
            image_path: Path to the image file.
            max_dimension: Maximum width or height (default: 1920px).

        Returns:
            Path to the processed image.

        Raises:
            PRDUploadError: If image processing fails.
        """
        try:
            img = Image.open(image_path)

            # Convert to RGB if necessary
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Resize if too large
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {new_size}")

            # Save optimized version
            processed_path = image_path.parent / f"processed_{image_path.name}"
            img.save(processed_path, optimize=True, quality=85)

            logger.info(f"Processed image: {processed_path}")
            return processed_path

        except Exception as e:
            raise PRDUploadError(f"Failed to process image {image_path}: {e}") from e

    def extract_text(self, file_path: Path) -> str:
        """Extract text from PDF/images (OCR if needed).

        Args:
            file_path: Path to the file.

        Returns:
            Extracted text content.
        """
        file_type = file_path.suffix.lower()

        # PDF text extraction
        if file_type == ".pdf":
            try:
                reader = PdfReader(file_path)
                text_parts = []

                for page_num, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")

                extracted_text = "\n\n".join(text_parts)
                logger.info(
                    f"Extracted {len(extracted_text)} characters from {len(reader.pages)} pages in PDF"
                )
                return extracted_text

            except Exception as e:
                logger.error(f"Failed to extract text from PDF {file_path}: {e}")
                return ""

        # TODO: Implement OCR with pytesseract for images
        logger.warning(
            f"Text extraction not implemented for {file_type} files. Consider using pytesseract for OCR."
        )
        return ""

    def upload(
        self,
        file_path: Path,
        process_images: bool = True,
        extract_text: bool = False,
    ) -> PRDDocument:
        """Upload and process PRD file.

        Args:
            file_path: Path to the PRD file.
            process_images: Whether to process/optimize images.
            extract_text: Whether to extract text content.

        Returns:
            PRDDocument instance.

        Raises:
            PRDUploadError: If upload fails.
            ValidationError: If document validation fails.
        """
        # Validate file
        self.validate_file(file_path)

        # Get file info
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        file_type = file_path.suffix.lower().lstrip(".")

        # Copy to storage directory
        stored_path = self.storage_dir / file_path.name
        if stored_path != file_path:
            import shutil

            shutil.copy2(file_path, stored_path)
            logger.info(f"Copied file to storage: {stored_path}")
        else:
            stored_path = file_path

        # Process images if applicable
        images: List[Path] = []
        if file_type in ("png", "jpg", "jpeg") and process_images:
            processed_img = self.process_image(stored_path)
            images.append(processed_img)

        # Extract text if requested or if text/PDF file
        content: Optional[str] = None
        if file_type in ("txt", "md"):
            # Read text/markdown files directly
            try:
                content = stored_path.read_text(encoding="utf-8")
                logger.info(f"Read text content from {stored_path.name}")
            except Exception as e:
                logger.error(f"Failed to read text file: {e}")
                content = ""
        elif file_type == "pdf":
            # Always extract text from PDFs
            content = self.extract_text(stored_path)
        elif extract_text:
            # Extract text from other file types if requested
            content = self.extract_text(stored_path)

        # Create PRDDocument
        try:
            doc = PRDDocument(
                file_path=stored_path,
                file_type=file_type,  # type: ignore
                uploaded_at=datetime.now(),
                file_size_mb=file_size_mb,
                content=content,
                images=images,
            )
            logger.info(f"Successfully uploaded PRD: {doc.file_path.name}")
            return doc

        except ValidationError as e:
            raise PRDUploadError(f"Document validation failed: {e}") from e

    def batch_upload(
        self,
        file_paths: List[Path],
        process_images: bool = True,
        extract_text: bool = False,
    ) -> List[PRDDocument]:
        """Upload multiple PRD files.

        Args:
            file_paths: List of file paths to upload.
            process_images: Whether to process/optimize images.
            extract_text: Whether to extract text content.

        Returns:
            List of PRDDocument instances.

        Raises:
            PRDUploadError: If any upload fails (partial failure allowed).
        """
        documents: List[PRDDocument] = []
        errors: List[tuple[Path, Exception]] = []

        for file_path in file_paths:
            try:
                doc = self.upload(
                    file_path, process_images=process_images, extract_text=extract_text
                )
                documents.append(doc)
            except Exception as e:
                logger.error(f"Failed to upload {file_path}: {e}")
                errors.append((file_path, e))

        if errors:
            error_summary = "; ".join([f"{p.name}: {e}" for p, e in errors])
            logger.warning(
                f"Batch upload completed with {len(errors)} errors: {error_summary}"
            )

        logger.info(
            f"Batch upload complete: {len(documents)}/{len(file_paths)} successful"
        )
        return documents
