from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from loguru import logger
import aiofiles
from pathlib import Path
import numpy as np
from PIL import Image
import io
from typing import List, Dict

# Configure logger to show timestamps
logger.remove()
logger.add(lambda msg: print(msg, flush=True), format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

load_dotenv()

app = FastAPI()

# Get the directory where main.py is located
BASE_DIR = Path(__file__).parent

class Point(BaseModel):
    x: float  # Normalized 0-1
    y: float  # Normalized 0-1

class Segment(BaseModel):
    id: int
    color: str
    area: float
    mask: List[Point]  # Polygon vertices defining the segment

class SegmentationResponse(BaseModel):
    message: str
    segments: List[Segment]
    dominant_colors: List[str]

class HealthCheck(BaseModel):
    status: str = "OK"
    media_path_exists: bool

@app.get("/")
def read_root() -> HealthCheck:
    """Health check endpoint."""
    media_path = Path(os.getenv("MEDIA_PATH", str(BASE_DIR / "media"))).resolve()
    logger.info("Using media path: {}", media_path)
    path_exists = os.path.exists(media_path)
    
    if not path_exists:
        logger.warning(f"Media path not found: {media_path}")
    else:
        logger.info("Media path exists and contains: {}", os.listdir(media_path))
    
    return HealthCheck(media_path_exists=path_exists)

@app.post("/segment")
async def segment_image(file_path: str):
    """
    Segment the image and extract dominant colors.
    For now, this returns mock data with actual segment boundaries.
    """
    try:
        logger.info("CV Service: Received segmentation request for file: {}", file_path)
        
        # Get the configured media path
        media_path = Path(os.getenv("MEDIA_PATH", str(BASE_DIR / "media"))).resolve()
        image_path = media_path / file_path
        
        logger.info("CV Service: Looking for image at: {}", image_path)
        if not image_path.exists():
            if media_path.exists():
                available_files = os.listdir(media_path)
                logger.error("CV Service: Image not found. Available files in media directory: {}", available_files)
            else:
                logger.error("CV Service: Media directory not found at: {}", media_path)
            raise HTTPException(status_code=404, detail="Image file not found")
            
        logger.info("CV Service: Image found, starting segmentation...")
        
        # TODO: Implement actual SAM segmentation
        # For now, return mock data with actual segment boundaries
        # These coordinates are normalized (0-1) relative to image dimensions
        mock_segments = [
            {
                "id": 1,
                "color": "#2B4C7E",  # Dark blue for the border
                "area": 0.3,
                "mask": [
                    {"x": 0, "y": 0},      # Top-left
                    {"x": 1, "y": 0},      # Top-right
                    {"x": 1, "y": 0.2},    # Right border
                    {"x": 0, "y": 0.2}     # Left border
                ]
            },
            {
                "id": 2,
                "color": "#567D46",  # Green for center
                "area": 0.5,
                "mask": [
                    {"x": 0.1, "y": 0.2},  # Top-left
                    {"x": 0.9, "y": 0.2},  # Top-right
                    {"x": 0.9, "y": 0.8},  # Bottom-right
                    {"x": 0.1, "y": 0.8}   # Bottom-left
                ]
            },
            {
                "id": 3,
                "color": "#2B4C7E",  # Dark blue for the border
                "area": 0.2,
                "mask": [
                    {"x": 0, "y": 0.8},    # Top-left
                    {"x": 1, "y": 0.8},    # Top-right
                    {"x": 1, "y": 1},      # Bottom-right
                    {"x": 0, "y": 1}       # Bottom-left
                ]
            }
        ]
        
        mock_colors = ["#2B4C7E", "#567D46", "#2B4C7E"]
        
        logger.info("CV Service: Segmentation complete. Found {} segments", len(mock_segments))
        logger.info("CV Service: Extracted {} dominant colors", len(mock_colors))
        
        response = SegmentationResponse(
            message="Segmentation completed",
            segments=mock_segments,
            dominant_colors=mock_colors
        )
        
        logger.info("CV Service: Sending response back to API")
        return response.dict()
        
    except Exception as e:
        logger.error("CV Service: Error during segmentation: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("CV Service: Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
