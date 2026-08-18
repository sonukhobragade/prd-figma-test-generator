"""Feature Management routes."""

import logging
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from framework.figma_client import FigmaClient
from framework.prd_uploader import PRDUploader
from routes.dependencies import PRD_STORAGE_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Feature Management"])

# Figma token from environment
FIGMA_TOKEN = os.getenv("FIGMA_API_TOKEN")


@router.get("/features")
async def list_features():
    """List all features.

    Returns:
        List of features with document counts.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()
    status = fm.get_status()

    if not status.get("enabled"):
        return JSONResponse(content={
            "success": False,
            "message": status.get("message", "Feature Manager not available"),
            "features": [],
        })

    features = fm.list_features()
    return JSONResponse(content={
        "success": True,
        "features": [f.to_dict() for f in features],
        "count": len(features),
    })


@router.post("/features")
async def create_feature(
    name: str = Form(...),
    keywords: str = Form(...),
    description: str = Form(""),
):
    """Create a new feature.

    Args:
        name: Feature name (display name).
        keywords: Comma-separated keywords for codebase linking.
        description: Optional description.

    Returns:
        Created feature.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    # Parse keywords
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    feature = fm.create_feature(
        name=name,
        keywords=keyword_list,
        description=description,
    )

    if not feature:
        raise HTTPException(status_code=500, detail="Failed to create feature")

    return JSONResponse(content={
        "success": True,
        "feature": feature.to_dict(),
    })


@router.get("/features/status")
async def get_features_status():
    """Get Feature Manager status.

    Returns:
        Status including feature count and document counts.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()
    status = fm.get_status()
    return JSONResponse(content=status)


@router.get("/features/{feature_id}")
async def get_feature(feature_id: str):
    """Get a feature by ID with all linked documents.

    Args:
        feature_id: Feature ID.

    Returns:
        Feature details with linked PRDs and Figma screens.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    feature = fm.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    # Get linked documents
    prds = fm.get_feature_documents(feature_id, doc_type="prd")
    figmas = fm.get_feature_documents(feature_id, doc_type="figma")

    return JSONResponse(content={
        "success": True,
        "feature": feature.to_dict(),
        "prds": [d.to_dict() for d in prds],
        "figmas": [d.to_dict() for d in figmas],
    })


@router.put("/features/{feature_id}")
async def update_feature(
    feature_id: str,
    name: str = Form(None),
    keywords: str = Form(None),
    description: str = Form(None),
):
    """Update a feature.

    Args:
        feature_id: Feature ID.
        name: New name (optional).
        keywords: New keywords (optional).
        description: New description (optional).

    Returns:
        Updated feature.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    keyword_list = None
    if keywords:
        keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    feature = fm.update_feature(
        feature_id=feature_id,
        name=name,
        keywords=keyword_list,
        description=description,
    )

    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found or update failed")

    return JSONResponse(content={
        "success": True,
        "feature": feature.to_dict(),
    })


@router.delete("/features/{feature_id}")
async def delete_feature(feature_id: str):
    """Delete a feature and all its linked documents.

    Args:
        feature_id: Feature ID.

    Returns:
        Success message.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    success = fm.delete_feature(feature_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete feature")

    return JSONResponse(content={
        "success": True,
        "message": f"Feature {feature_id} deleted",
    })


@router.post("/features/{feature_id}/prd")
async def add_prd_to_feature(
    feature_id: str,
    file: UploadFile = File(...),
):
    """Upload a PRD document to a feature.

    Args:
        feature_id: Feature ID.
        file: PRD file (PDF, PNG, JPG).

    Returns:
        Created document.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    # Verify feature exists
    feature = fm.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    # Save and process file
    file_path = PRD_STORAGE_DIR / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Extract text from PRD
    uploader = PRDUploader()
    prd_doc = uploader.upload(file_path)

    # Add to feature
    doc = fm.add_document(
        feature_id=feature_id,
        doc_type="prd",
        name=file.filename,
        content=prd_doc.content or "",
        metadata={
            "file_path": str(file_path),
            "original_filename": file.filename,
        }
    )

    if not doc:
        raise HTTPException(status_code=500, detail="Failed to add PRD to feature")

    return JSONResponse(content={
        "success": True,
        "document": doc.to_dict(),
    })


@router.post("/features/{feature_id}/figma")
async def add_figma_to_feature(
    feature_id: str,
    figma_url: str = Form(...),
    screen_name: str = Form(None),
):
    """Add a Figma screen to a feature.

    Args:
        feature_id: Feature ID.
        figma_url: Figma URL.
        screen_name: Optional screen name override.

    Returns:
        Created document.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    # Verify feature exists
    feature = fm.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    # Validate Figma token
    if not FIGMA_TOKEN:
        raise HTTPException(status_code=400, detail="FIGMA_API_TOKEN not configured")

    # Extract Figma data
    figma_client = FigmaClient(api_token=FIGMA_TOKEN)
    file_key, node_id = figma_client.parse_figma_url(figma_url)
    figma_structure = figma_client.extract_ui_elements(file_key, node_id)

    # Build content from Figma structure
    content_parts = [
        f"File: {figma_structure.get('file_name', 'Unknown')}",
        f"Components: {len(figma_structure.get('components', []))}",
    ]

    if figma_structure.get('text_elements'):
        content_parts.append(f"Text elements: {len(figma_structure['text_elements'])}")
        content_parts.append("Text content:")
        for text in figma_structure['text_elements'][:20]:
            if isinstance(text, dict):
                content_parts.append(f"  - {text.get('text', '')}")
            else:
                content_parts.append(f"  - {text}")

    content = "\n".join(content_parts)

    # Add to feature
    doc = fm.add_document(
        feature_id=feature_id,
        doc_type="figma",
        name=screen_name or figma_structure.get("file_name", "Figma Screen"),
        content=content,
        metadata={
            "figma_url": figma_url,
            "file_key": file_key,
            "node_id": node_id,
            "file_name": figma_structure.get("file_name"),
            "component_count": len(figma_structure.get("components", [])),
        }
    )

    if not doc:
        raise HTTPException(status_code=500, detail="Failed to add Figma to feature")

    return JSONResponse(content={
        "success": True,
        "document": doc.to_dict(),
    })


@router.delete("/features/{feature_id}/documents/{doc_id}")
async def delete_feature_document(feature_id: str, doc_id: str):
    """Delete a document from a feature.

    Args:
        feature_id: Feature ID (for validation).
        doc_id: Document ID.

    Returns:
        Success message.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    success = fm.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete document")

    return JSONResponse(content={
        "success": True,
        "message": f"Document {doc_id} deleted",
    })


@router.get("/features/{feature_id}/context")
async def get_feature_context(feature_id: str):
    """Get all context for a feature (for test generation).

    Args:
        feature_id: Feature ID.

    Returns:
        Combined PRD, Figma, and Codebase context.
    """
    from framework.feature_manager import get_feature_manager

    fm = get_feature_manager()

    feature = fm.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    context = fm.get_feature_context(feature_id)

    return JSONResponse(content={
        "success": True,
        "feature": feature.to_dict(),
        "context": context,
    })
