"""VLM Analysis Router — POST /api/vlm/analyze

Accepts a pre/post image pair and returns per-building damage predictions
produced by Gemini. No database writes; purely synchronous inference.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.services.vlm_service import analyze_scene

router = APIRouter(prefix="/api/vlm", tags=["VLM Analysis"])


class DamageCounts(BaseModel):
    no_damage: int = 0
    minor_damage: int = 0
    major_damage: int = 0
    destroyed: int = 0


class SceneAnalysisResponse(BaseModel):
    buildings_visible: int
    damage_counts: DamageCounts
    scene_summary: str
    model_used: str
    error: str | None = None


@router.post("/analyze", response_model=SceneAnalysisResponse)
async def analyze_scene_endpoint(
    post_image: UploadFile = File(..., description="Post-disaster image (JPEG/PNG/TIFF)"),
):
    """Send a post-disaster image to Gemini and return damage counts for the scene."""
    post_bytes = await post_image.read()

    if not post_bytes:
        raise HTTPException(status_code=422, detail="post_image must be non-empty.")

    result = analyze_scene(post_image_bytes=post_bytes)

    if result.get("error") and not result.get("buildings_visible"):
        raise HTTPException(status_code=502, detail=result["error"])

    counts = result.get("damage_counts") or {}
    return SceneAnalysisResponse(
        buildings_visible=result.get("buildings_visible", 0),
        damage_counts=DamageCounts(**{k: counts.get(k, 0) for k in ["no_damage", "minor_damage", "major_damage", "destroyed"]}),
        scene_summary=result.get("scene_summary", ""),
        model_used=result.get("model_used", ""),
        error=result.get("error"),
    )
