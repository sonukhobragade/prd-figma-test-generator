"""Comprehensive tests for framework.figma_client module."""

from unittest.mock import Mock, patch

import pytest
import requests

from framework.figma_client import FigmaAPIError, FigmaClient


class TestFigmaClientInit:
    """Tests for FigmaClient initialization."""

    def test_init_creates_storage_dir(self, tmp_path):
        """Test initialization creates storage directory."""
        storage_dir = tmp_path / "figma_storage"
        client = FigmaClient(api_token="test_token", storage_dir=storage_dir)

        assert storage_dir.exists()
        assert client.api_token == "test_token"
        assert client.storage_dir == storage_dir

    def test_init_sets_headers(self, tmp_path):
        """Test initialization sets correct API headers."""
        client = FigmaClient(api_token="secret_token", storage_dir=tmp_path)

        assert "X-Figma-Token" in client.session.headers
        assert client.session.headers["X-Figma-Token"] == "secret_token"


class TestParseFigmaUrl:
    """Tests for parse_figma_url.

    Figma writes node ids as ``1-2`` in the URL but the REST API addresses
    them as ``1:2``. parse_figma_url converts, which is what the rest of the
    client depends on. The previous tests asserted the URL spelling came back
    unchanged, which would have broken every API call built from it.
    """

    @pytest.fixture
    def client(self, tmp_path):
        return FigmaClient(api_token="test", storage_dir=tmp_path)

    def test_file_url(self, client):
        key, node = client.parse_figma_url(
            "https://www.figma.com/file/abc123/Design?node-id=1:2"
        )
        assert (key, node) == ("abc123", "1:2")

    def test_percent_encoded_colon(self, client):
        """A URL copied from the browser carries node-id=123%3A456; the
        encoded colon truncated the id to "123"."""
        key, node = client.parse_figma_url(
            "https://www.figma.com/design/abc123/App?node-id=123%3A456"
        )
        assert (key, node) == ("abc123", "123:456")

    def test_design_url_converts_dash_to_colon(self, client):
        key, node = client.parse_figma_url(
            "https://www.figma.com/design/xyz789/Project?node-id=10-20"
        )
        assert (key, node) == ("xyz789", "10:20")

    def test_url_without_node_id(self, client):
        key, node = client.parse_figma_url("https://figma.com/design/abc123/MyApp")
        assert key == "abc123"
        assert node is None

    def test_invalid_url_raises(self, client):
        with pytest.raises(FigmaAPIError, match="Invalid Figma URL"):
            client.parse_figma_url("https://example.com/not-figma")


class TestGetFileMetadata:
    """Tests for get_file_metadata (previously get_file_data)."""

    @pytest.fixture
    def client(self, tmp_path):
        return FigmaClient(api_token="test", storage_dir=tmp_path)

    def test_returns_parsed_json(self, client):
        payload = {"name": "My Design", "document": {"id": "0:0"}}
        with patch.object(client.session, "get") as get:
            get.return_value = _response(json_body=payload)
            assert client.get_file_metadata("abc123") == payload
        assert "/files/abc123" in get.call_args.args[0]

    def test_http_error_raises_figma_error(self, client):
        with patch.object(client.session, "get") as get:
            get.return_value = _response(status=404)
            with pytest.raises(FigmaAPIError):
                client.get_file_metadata("missing")


class TestGetScreenshot:
    """Tests for get_screenshot (previously download_image).

    It returns image bytes rather than a path.
    """

    @pytest.fixture
    def client(self, tmp_path):
        return FigmaClient(api_token="test", storage_dir=tmp_path)

    def test_returns_image_bytes(self, client):
        images = {"images": {"1:2": "https://example.test/image.png"}}
        with patch.object(client.session, "get") as api_get, \
             patch("framework.figma_client.requests.get") as img_get:
            api_get.return_value = _response(json_body=images)
            img_get.return_value = _response(content=b"\x89PNG\r\n")
            data = client.get_screenshot("abc123", "1:2")
        assert data == b"\x89PNG\r\n"

    def test_missing_node_raises(self, client):
        with patch.object(client.session, "get") as api_get:
            api_get.return_value = _response(json_body={"images": {}})
            with pytest.raises(FigmaAPIError, match="No image URL"):
                client.get_screenshot("abc123", "1:2")

    def test_empty_url_raises(self, client):
        with patch.object(client.session, "get") as api_get:
            api_get.return_value = _response(json_body={"images": {"1:2": None}})
            with pytest.raises(FigmaAPIError, match="Empty image URL"):
                client.get_screenshot("abc123", "1:2")


def _response(json_body=None, content=b"", status=200):
    """A requests-like double. raise_for_status honours the status code."""
    resp = Mock()
    resp.status_code = status
    resp.content = content
    resp.json.return_value = json_body if json_body is not None else {}
    if status >= 400:
        err = requests.exceptions.HTTPError(f"HTTP {status}")
        err.response = resp
        resp.raise_for_status.side_effect = err
    else:
        resp.raise_for_status.return_value = None
    return resp
