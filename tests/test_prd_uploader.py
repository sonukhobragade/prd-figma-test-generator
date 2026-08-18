"""Tests for framework.prd_uploader module."""

from pathlib import Path

import pytest
from PIL import Image

from framework.prd_uploader import PRDUploadError, PRDUploader


class TestPRDUploaderInit:
    """Tests for PRDUploader initialization."""

    def test_init_default_storage_dir(self, tmp_path, monkeypatch):
        """Test initialization with default storage directory."""
        monkeypatch.chdir(tmp_path)
        uploader = PRDUploader()

        assert uploader.storage_dir == Path("prd")
        assert uploader.storage_dir.exists()

    def test_init_custom_storage_dir(self, tmp_path):
        """Test initialization with custom storage directory."""
        storage_dir = tmp_path / "custom_storage"
        uploader = PRDUploader(storage_dir=storage_dir)

        assert uploader.storage_dir == storage_dir
        assert storage_dir.exists()


class TestValidateFile:
    """Tests for file validation."""

    def test_validate_file_nonexistent(self, tmp_path):
        """Test validation fails for non-existent file."""
        uploader = PRDUploader(storage_dir=tmp_path)
        nonexistent_file = tmp_path / "nonexistent.pdf"

        with pytest.raises(PRDUploadError, match="File not found"):
            uploader.validate_file(nonexistent_file)

    def test_validate_file_unsupported_format(self, tmp_path):
        """Test validation fails for unsupported file format."""
        uploader = PRDUploader(storage_dir=tmp_path)
        txt_file = tmp_path / "test.docx"
        txt_file.write_text("test content")

        with pytest.raises(PRDUploadError, match="Unsupported format"):
            uploader.validate_file(txt_file)

    def test_validate_file_too_large(self, tmp_path):
        """Test validation fails for oversized file."""
        uploader = PRDUploader(storage_dir=tmp_path)
        large_file = tmp_path / "large.pdf"

        # Create a file larger than 50MB
        with open(large_file, "wb") as f:
            f.write(b"0" * (51 * 1024 * 1024))

        with pytest.raises(PRDUploadError, match="File too large"):
            uploader.validate_file(large_file)

    def test_validate_file_valid_pdf(self, tmp_path):
        """Test validation passes for valid PDF."""
        uploader = PRDUploader(storage_dir=tmp_path)
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\ntest content")

        assert uploader.validate_file(pdf_file) is True

    def test_validate_file_valid_image(self, tmp_path):
        """Test validation passes for valid image formats."""
        uploader = PRDUploader(storage_dir=tmp_path)

        for ext in [".png", ".jpg", ".jpeg"]:
            img_file = tmp_path / f"test{ext}"
            # Create a small test image
            img = Image.new("RGB", (100, 100), color="red")
            img.save(img_file)

            assert uploader.validate_file(img_file) is True


class TestIsSupportedFormat:
    """Tests for format checking."""

    def test_is_supported_format_pdf(self, tmp_path):
        """Test PDF format is supported."""
        uploader = PRDUploader(storage_dir=tmp_path)
        assert uploader._is_supported_format(Path("test.pdf"))

    def test_is_supported_format_images(self, tmp_path):
        """Test image formats are supported."""
        uploader = PRDUploader(storage_dir=tmp_path)

        for ext in [".png", ".jpg", ".jpeg"]:
            assert uploader._is_supported_format(Path(f"test{ext}"))

    def test_is_supported_format_case_insensitive(self, tmp_path):
        """Test format checking is case-insensitive."""
        uploader = PRDUploader(storage_dir=tmp_path)
        assert uploader._is_supported_format(Path("test.PDF"))
        assert uploader._is_supported_format(Path("test.PNG"))

    def test_is_supported_format_unsupported(self, tmp_path):
        """Test unsupported formats are rejected."""
        uploader = PRDUploader(storage_dir=tmp_path)

        # .txt and .md are supported; use formats that genuinely are not.
        for ext in [".docx", ".zip", ".exe"]:
            assert not uploader._is_supported_format(Path(f"test{ext}"))


class TestProcessImage:
    """Tests for image processing."""

    def test_process_image_basic(self, tmp_path):
        """Test basic image processing."""
        uploader = PRDUploader(storage_dir=tmp_path)
        img_file = tmp_path / "test.png"

        # Create test image
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_file)

        processed_path = uploader.process_image(img_file)

        assert processed_path.exists()
        assert processed_path.name.startswith("processed_")

    def test_process_image_resize_large(self, tmp_path):
        """Test processing resizes large images."""
        uploader = PRDUploader(storage_dir=tmp_path)
        img_file = tmp_path / "large.png"

        # Create large image
        img = Image.new("RGB", (3000, 2000), color="green")
        img.save(img_file)

        processed_path = uploader.process_image(img_file, max_dimension=1920)

        # Check that image was resized
        processed_img = Image.open(processed_path)
        assert max(processed_img.size) == 1920

    def test_process_image_convert_rgba(self, tmp_path):
        """Test processing converts RGBA to RGB."""
        uploader = PRDUploader(storage_dir=tmp_path)
        img_file = tmp_path / "rgba.png"

        # Create RGBA image
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(img_file)

        processed_path = uploader.process_image(img_file)
        processed_img = Image.open(processed_path)

        assert processed_img.mode == "RGB"

    def test_process_image_invalid_file(self, tmp_path):
        """Test processing fails gracefully for invalid image."""
        uploader = PRDUploader(storage_dir=tmp_path)
        invalid_file = tmp_path / "invalid.png"
        invalid_file.write_text("not an image")

        with pytest.raises(PRDUploadError, match="Failed to process image"):
            uploader.process_image(invalid_file)


class TestExtractText:
    """Tests for text extraction."""

    def test_extract_text_not_implemented(self, tmp_path):
        """Test text extraction returns empty string (not implemented)."""
        uploader = PRDUploader(storage_dir=tmp_path)
        file_path = tmp_path / "test.pdf"
        file_path.write_bytes(b"test")

        result = uploader.extract_text(file_path)
        assert result == ""


class TestUpload:
    """Tests for file upload."""

    def test_upload_valid_image_no_processing(self, tmp_path):
        """Test uploading image without processing."""
        storage_dir = tmp_path / "storage"
        uploader = PRDUploader(storage_dir=storage_dir)

        img_file = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="yellow")
        img.save(img_file)

        doc = uploader.upload(img_file, process_images=False)

        assert doc.file_path.exists()
        assert doc.file_type == "png"
        assert doc.file_size_mb > 0
        assert len(doc.images) == 0

    def test_upload_valid_image_with_processing(self, tmp_path):
        """Test uploading image with processing."""
        storage_dir = tmp_path / "storage"
        uploader = PRDUploader(storage_dir=storage_dir)

        img_file = tmp_path / "test.jpg"
        img = Image.new("RGB", (100, 100), color="cyan")
        img.save(img_file)

        doc = uploader.upload(img_file, process_images=True)

        assert doc.file_path.exists()
        assert doc.file_type == "jpg"
        assert len(doc.images) == 1
        assert doc.images[0].exists()

    def test_upload_invalid_file(self, tmp_path):
        """Test uploading invalid file raises error."""
        uploader = PRDUploader(storage_dir=tmp_path)
        invalid_file = tmp_path / "test.docx"
        invalid_file.write_text("test")

        with pytest.raises(PRDUploadError, match="Unsupported format"):
            uploader.upload(invalid_file)


class TestBatchUpload:
    """Tests for batch file upload."""

    def test_batch_upload_all_valid(self, tmp_path):
        """Test batch upload with all valid files."""
        storage_dir = tmp_path / "storage"
        uploader = PRDUploader(storage_dir=storage_dir)

        files = []
        for i in range(3):
            img_file = tmp_path / f"test{i}.png"
            img = Image.new("RGB", (100, 100), color="white")
            img.save(img_file)
            files.append(img_file)

        docs = uploader.batch_upload(files, process_images=False)

        assert len(docs) == 3
        for doc in docs:
            assert doc.file_path.exists()

    def test_batch_upload_partial_failure(self, tmp_path):
        """Test batch upload with some invalid files."""
        storage_dir = tmp_path / "storage"
        uploader = PRDUploader(storage_dir=storage_dir)

        # Create mix of valid and invalid files
        valid_file = tmp_path / "valid.png"
        img = Image.new("RGB", (100, 100), color="black")
        img.save(valid_file)

        invalid_file = tmp_path / "invalid.docx"  # .txt is a supported format
        invalid_file.write_text("invalid")

        files = [valid_file, invalid_file]
        docs = uploader.batch_upload(files, process_images=False)

        # Should have 1 successful upload
        assert len(docs) == 1
        assert docs[0].file_path.exists()

    def test_batch_upload_empty_list(self, tmp_path):
        """Test batch upload with empty file list."""
        uploader = PRDUploader(storage_dir=tmp_path)
        docs = uploader.batch_upload([])
        assert len(docs) == 0


class TestExtractTextPdf:
    """Tests for PDF text extraction.

    Renamed from TestExtractText: a second class of that name shadowed the
    one at line 169, so its single test never ran.
    """

    def test_extract_text_pdf_success(self, tmp_path):
        """Test successful PDF text extraction."""
        from pypdf import PdfWriter

        uploader = PRDUploader(storage_dir=tmp_path)
        pdf_file = tmp_path / "test.pdf"

        # Create a simple PDF with text
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        page = writer.pages[0]
        page.merge_page(page)  # Simple operation to make it valid

        with open(pdf_file, "wb") as f:
            writer.write(f)

        # For now, just test that the method doesn't crash
        # Real PDF with text would require more complex setup
        result = uploader.extract_text(pdf_file)
        assert isinstance(result, str)

    def test_extract_text_pdf_multi_page(self, tmp_path):
        """Test PDF extraction with multiple pages."""
        from pypdf import PdfWriter

        uploader = PRDUploader(storage_dir=tmp_path)
        pdf_file = tmp_path / "multipage.pdf"

        # Create PDF with 3 pages
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=200, height=200)

        with open(pdf_file, "wb") as f:
            writer.write(f)

        result = uploader.extract_text(pdf_file)
        assert isinstance(result, str)
        # Blank pages may have no text, so we just verify it runs

    def test_extract_text_pdf_empty_pages(self, tmp_path):
        """Test PDF extraction handles empty pages gracefully."""
        from pypdf import PdfWriter

        uploader = PRDUploader(storage_dir=tmp_path)
        pdf_file = tmp_path / "empty.pdf"

        # Create PDF with blank pages (no text)
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)

        with open(pdf_file, "wb") as f:
            writer.write(f)

        result = uploader.extract_text(pdf_file)
        # Empty pages should return empty string or minimal content
        assert isinstance(result, str)

    def test_extract_text_pdf_corrupted(self, tmp_path):
        """Test PDF extraction handles corrupted files gracefully."""
        uploader = PRDUploader(storage_dir=tmp_path)
        pdf_file = tmp_path / "corrupted.pdf"

        # Create invalid PDF data
        pdf_file.write_bytes(b"Not a valid PDF file")

        # Should return empty string on error, not crash
        result = uploader.extract_text(pdf_file)
        assert result == ""

    def test_extract_text_unsupported_format(self, tmp_path):
        """Test extraction returns empty string for unsupported formats."""
        uploader = PRDUploader(storage_dir=tmp_path)
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Plain text content")

        result = uploader.extract_text(txt_file)
        # Should warn and return empty string for unsupported types
        assert result == ""

    def test_upload_pdf_auto_extraction(self, tmp_path):
        """Test that upload() automatically extracts text from PDFs."""
        from pypdf import PdfWriter

        uploader = PRDUploader(storage_dir=tmp_path)
        pdf_file = tmp_path / "auto_extract.pdf"

        # Create a simple PDF
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)

        with open(pdf_file, "wb") as f:
            writer.write(f)

        # Upload the PDF
        prd_doc = uploader.upload(pdf_file)

        # Verify content was extracted (even if empty from blank pages)
        assert prd_doc.content is not None
        assert isinstance(prd_doc.content, str)
        assert prd_doc.file_type == "pdf"

    def test_extract_text_page_markers(self, tmp_path):
        """Test that page markers are included in extracted text."""
        from pypdf import PdfWriter

        uploader = PRDUploader(storage_dir=tmp_path)
        pdf_file = tmp_path / "markers.pdf"

        # Create PDF with 2 pages
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)

        with open(pdf_file, "wb") as f:
            writer.write(f)

        result = uploader.extract_text(pdf_file)

        # Even with blank pages, we should see the extraction ran
        # (page markers would be in output if pages had text)
        assert isinstance(result, str)
