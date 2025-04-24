from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field, validator
import os
from dotenv import load_dotenv
from loguru import logger
import aiofiles
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
import io
from typing import List, Dict, Optional
import torch
from segment_anything import sam_model_registry, SamPredictor, SamAutomaticMaskGenerator
from sklearn.cluster import KMeans
import colorsys
import time
import uuid

# Configure logger to show timestamps
logger.remove()
logger.add(lambda msg: print(msg, flush=True), format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

load_dotenv()

app = FastAPI()

# Get the directory where main.py is located
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent

# Get media path from environment or use default
MEDIA_PATH = Path(os.getenv("MEDIA_PATH", str(PROJECT_ROOT / "api" / "media")))
if not MEDIA_PATH.exists():
    MEDIA_PATH.mkdir(parents=True, exist_ok=True)
logger.info(f"Using media path: {MEDIA_PATH}")

# Test image path
TEST_IMAGE_PATH = PROJECT_ROOT / "block-colors-01.jpg"

# Initialize SAM and MaskGenerator
try:
    CHECKPOINT_PATH = BASE_DIR / "models" / "sam_vit_h_4b8939.pth"
    if not CHECKPOINT_PATH.exists():
        logger.error(f"SAM model checkpoint not found at {CHECKPOINT_PATH}")
        raise FileNotFoundError(f"SAM model checkpoint not found at {CHECKPOINT_PATH}")
        
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Using device: {DEVICE}")
    
    sam = sam_model_registry["vit_h"](checkpoint=str(CHECKPOINT_PATH))
    sam.to(device=DEVICE)
    predictor = SamPredictor(sam)
    
    # Initialize Automatic Mask Generator with optimized parameters
    mask_generator = SamAutomaticMaskGenerator(
        model=sam,
        points_per_side=32,
        pred_iou_thresh=0.88,
        stability_score_thresh=0.95,
        min_mask_region_area=100
    )
    logger.info("SAM model and MaskGenerator initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize SAM model: {str(e)}")
    raise

# Configuration
MAX_IMAGE_SIZE = 4096  # Maximum dimension of input image
MIN_IMAGE_SIZE = 100   # Minimum dimension of input image
SEGMENTATION_CONFIG = {
    "points_per_side": 32,
    "pred_iou_thresh": 0.88,
    "stability_score_thresh": 0.95,
    "min_mask_region_area": 100,
    "min_relative_area": 0.01  # Minimum segment area relative to image
}

class Point(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)  # Normalized 0-1
    y: float = Field(..., ge=0.0, le=1.0)  # Normalized 0-1

class Segment(BaseModel):
    id: int = Field(..., gt=0)
    color: str = Field(..., pattern="^#[0-9a-fA-F]{6}$")  # Hex color validation
    area: float = Field(..., gt=0.0, le=1.0)  # Normalized area
    mask: List[Point]  # Polygon vertices defining the segment
    score: float = Field(..., ge=0.0, le=1.0)  # IoU score

    @validator('score')
    def clamp_score(cls, v):
        return min(v, 1.0)  # Clamp score to maximum of 1.0

class SegmentationResponse(BaseModel):
    message: str
    segments: List[Segment]
    dominant_colors: List[str]
    debug_image_path: str = ""

class HealthCheck(BaseModel):
    status: str = "OK"
    media_path_exists: bool

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex color code."""
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def get_dominant_colors(image: np.ndarray, n_colors: int = 3) -> List[str]:
    """Extract dominant colors from image using K-means clustering."""
    # Convert BGR to RGB first
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Reshape image to be a list of pixels
    pixels = image_rgb.reshape(-1, 3)
    
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=n_colors, random_state=42)
    kmeans.fit(pixels)
    
    # Get the colors
    colors = kmeans.cluster_centers_
    
    # Convert to hex
    hex_colors = [rgb_to_hex(color) for color in colors]
    
    return hex_colors

def create_debug_visualization(image: np.ndarray, segments: List[Dict], output_path: str) -> str:
    """Create an enhanced debug visualization of the segments."""
    # Create a copy of the image for visualization
    debug_image = image.copy()
    overlay = debug_image.copy()
    
    # Draw each segment
    for segment in segments:
        # Convert normalized points back to image coordinates
        points = []
        for point in segment["mask"]:
            x = int(point["x"] * image.shape[1])
            y = int(point["y"] * image.shape[0])
            points.append([x, y])
        
        points = np.array(points, dtype=np.int32)
        
        # Use segment's actual color
        hex_color = segment["color"]
        color = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))  # Convert hex to BGR
        
        # Draw filled contour with semi-transparency
        cv2.fillPoly(overlay, [points], color)
        
        # Draw border
        cv2.polylines(debug_image, [points], True, (255, 255, 255), 2)
        
        # Add segment info with outline for better visibility
        centroid = points.mean(axis=0).astype(int)
        text = f"{segment['id']} ({segment['score']:.2f})"
        
        # Draw text outline
        cv2.putText(debug_image, text, tuple(centroid), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3)
        # Draw text in white
        cv2.putText(debug_image, text, tuple(centroid), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
    
    # Blend the filled overlay with the original image
    cv2.addWeighted(overlay, 0.5, debug_image, 0.5, 0, debug_image)
    
    # Save debug image
    cv2.imwrite(str(output_path), debug_image)
    return str(output_path)

def validate_image(image: np.ndarray) -> None:
    """Validate image dimensions and content."""
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image data")
        
    h, w = image.shape[:2]
    if h < MIN_IMAGE_SIZE or w < MIN_IMAGE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"Image too small. Minimum dimension is {MIN_IMAGE_SIZE}px"
        )
    if h > MAX_IMAGE_SIZE or w > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"Image too large. Maximum dimension is {MAX_IMAGE_SIZE}px"
        )

def get_unique_path(base_path: Path, suffix: str) -> Path:
    """Generate unique file path to avoid overwrites."""
    if not base_path.exists():
        return base_path
    
    stem = base_path.stem
    parent = base_path.parent
    unique_id = str(uuid.uuid4())[:8]
    return parent / f"{stem}_{unique_id}{suffix}"

def cleanup_old_files(directory: Path, pattern: str, max_age_hours: int = 24) -> None:
    """Clean up old debug files."""
    try:
        current_time = time.time()
        for file in directory.glob(pattern):
            if (current_time - file.stat().st_mtime) > max_age_hours * 3600:
                file.unlink()
    except Exception as e:
        logger.warning(f"Failed to cleanup old files: {e}")

def find_contours(image: np.ndarray) -> List[Dict]:
    """Find segments in the image using SAM's Automatic Mask Generator."""
    try:
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]
        
        # Generate masks automatically
        logger.info("Starting automatic mask generation...")
        start_time = time.time()
        masks_data = mask_generator.generate(image_rgb)
        end_time = time.time()
        logger.info(f"Automatic mask generation finished in {end_time - start_time:.2f} seconds")
        logger.info(f"Generated {len(masks_data)} raw masks")
        
        segments = []
        total_area = h * w
        
        for i, mask_info in enumerate(masks_data):
            mask = mask_info['segmentation']
            score = mask_info['predicted_iou']
            area = mask_info['area']
            
            # Filter by relative area
            if area < total_area * SEGMENTATION_CONFIG["min_relative_area"]:
                continue
                
            logger.info(f"Processing segment {i}: Area={area}, Predicted IoU={score:.3f}")
            
            # Find contours in the mask
            mask_uint8 = mask.astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                # Simplify contour
                epsilon = 0.005 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Convert to normalized coordinates and validate points
                points = []
                for point in approx:
                    x = float(point[0][0]) / w
                    y = float(point[0][1]) / h
                    # Validate point through model
                    point_model = Point(x=x, y=y)
                    points.append(point_model)
                
                # Calculate mean color for the segment
                mask_3d = np.stack([mask] * 3, axis=2)
                segment_pixels = image_rgb[mask]
                mean_color = segment_pixels.mean(axis=0)
                hex_color = rgb_to_hex(mean_color)
                
                # Create and validate segment through model
                segment = Segment(
                    id=len(segments) + 1,
                    color=hex_color,
                    area=float(area) / total_area,
                    mask=points,
                    score=min(float(score), 1.0)  # Clamp score to 1.0 before validation
                )
                segments.append(segment.dict())  # Store as dict for serialization
        
        logger.info(f"Found {len(segments)} segments after filtering")
        return segments
        
    except Exception as e:
        logger.error(f"Segmentation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(e)}")
    finally:
        # Cleanup to help with memory
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

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

@app.get("/test")
async def test_segmentation():
    """Test endpoint using block-colors-01.jpg."""
    try:
        logger.info(f"Running test segmentation with {TEST_IMAGE_PATH}")
        
        if not TEST_IMAGE_PATH.exists():
            raise HTTPException(status_code=404, detail="Test image not found")
            
        image = cv2.imread(str(TEST_IMAGE_PATH))
        if image is None:
            raise HTTPException(status_code=400, detail="Failed to read test image")
        
        # Find segments
        segments = find_contours(image)
        
        # Get dominant colors
        dominant_colors = get_dominant_colors(image)
        
        # Create debug visualization
        debug_path = TEST_IMAGE_PATH.with_suffix('.debug.jpg')
        create_debug_visualization(image, segments, debug_path)
        
        response = SegmentationResponse(
            message=f"Successfully segmented test image into {len(segments)} regions",
            segments=[Segment(**s) for s in segments],  # Validate against model
            dominant_colors=dominant_colors,
            debug_image_path=str(debug_path)
        )
        
        logger.info(f"Test complete. Found {len(segments)} segments.")
        return response.dict()
        
    except Exception as e:
        logger.error(f"Test segmentation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/segment")
async def segment_image(file_path: str):
    """Segment an uploaded image."""
    try:
        # Convert to Path object and ensure it's in the media directory
        file_path = MEDIA_PATH / Path(file_path).name
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
            
        # Read and validate image
        image = cv2.imread(str(file_path))
        validate_image(image)
        
        logger.info(f"Processing image: {file_path}")
        logger.info(f"Image shape: {image.shape}")
        
        # Find segments
        segments = find_contours(image)
        
        # Get dominant colors
        dominant_colors = get_dominant_colors(image)
        
        # Create debug visualization with unique path
        debug_path = get_unique_path(
            file_path.with_suffix('.debug.jpg'),
            '.jpg'
        )
        create_debug_visualization(image, segments, debug_path)
        
        # Cleanup old debug files
        cleanup_old_files(debug_path.parent, "*.debug.jpg")
        
        # Create response
        response = SegmentationResponse(
            message=f"Successfully segmented image into {len(segments)} regions",
            segments=[Segment(**s) for s in segments],
            dominant_colors=dominant_colors,
            debug_image_path=str(debug_path)
        )
        
        logger.info(f"Segmentation complete. Found {len(segments)} segments.")
        logger.info(f"Debug visualization saved to: {debug_path}")
        
        return response.dict()
        
    except Exception as e:
        logger.error(f"Segmentation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("CV Service: Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
