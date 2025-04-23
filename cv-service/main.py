from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from loguru import logger
import aiofiles
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
import io
from typing import List, Dict
import torch
from segment_anything import sam_model_registry, SamPredictor
from sklearn.cluster import KMeans
import colorsys

# Configure logger to show timestamps
logger.remove()
logger.add(lambda msg: print(msg, flush=True), format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

load_dotenv()

app = FastAPI()

# Get the directory where main.py is located
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent

# Test image path
TEST_IMAGE_PATH = PROJECT_ROOT / "block-colors-01.jpg"

# Initialize SAM
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
    logger.info("SAM model initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize SAM model: {str(e)}")
    raise

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
    debug_image_path: str = ""  # Path to debug visualization

class HealthCheck(BaseModel):
    status: str = "OK"
    media_path_exists: bool

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex color code."""
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def get_dominant_colors(image: np.ndarray, n_colors: int = 3) -> List[str]:
    """Extract dominant colors from image using K-means clustering."""
    # Reshape image to be a list of pixels
    pixels = image.reshape(-1, 3)
    
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=n_colors, random_state=42)
    kmeans.fit(pixels)
    
    # Get the colors
    colors = kmeans.cluster_centers_
    
    # Convert to hex
    hex_colors = [rgb_to_hex(color) for color in colors]
    
    return hex_colors

def create_debug_visualization(image: np.ndarray, segments: List[Dict], output_path: str) -> str:
    """Create a debug visualization of the segments."""
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
        
        # Convert points to numpy array
        points = np.array(points, dtype=np.int32)
        
        # Draw filled contour with segment color
        color = tuple(int(segment["color"][i:i+2], 16) for i in (1, 3, 5))  # Convert hex to BGR
        cv2.fillPoly(overlay, [points], color)
        
        # Draw border in white for visibility
        cv2.polylines(debug_image, [points], True, (255, 255, 255), 2)
        
        # Add segment ID with outline for better visibility
        centroid = points.mean(axis=0).astype(int)
        # Draw text outline
        cv2.putText(debug_image, str(segment["id"]), tuple(centroid), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3)
        # Draw text in white
        cv2.putText(debug_image, str(segment["id"]), tuple(centroid), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
    
    # Blend the filled overlay with the original image
    cv2.addWeighted(overlay, 0.5, debug_image, 0.5, 0, debug_image)
    
    # Save debug image
    cv2.imwrite(output_path, debug_image)
    return output_path

def find_contours(image: np.ndarray) -> List[Dict]:
    """Find segments in the image using SAM."""
    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Set image in predictor
    predictor.set_image(image_rgb)
    
    # Generate automatic mask proposals using points
    h, w = image.shape[:2]
    points_per_side = 32
    points_y = np.linspace(0, h-1, points_per_side)
    points_x = np.linspace(0, w-1, points_per_side)
    points = []
    for x in points_x:
        for y in points_y:
            points.append([x, y])
    points = np.array(points)
    
    # Reshape points to match expected input shape [N, 2]
    input_points = points.reshape(-1, 2)
    input_labels = np.ones(len(input_points))
    
    # Get predictions for all points
    masks = []
    scores = []
    
    # Process points in batches
    batch_size = 64
    for i in range(0, len(input_points), batch_size):
        batch_points = input_points[i:i+batch_size]
        batch_labels = input_labels[i:i+batch_size]
        
        # Prepare input tensors with correct dimensions
        point_coords = torch.from_numpy(batch_points).unsqueeze(0)  # Add batch dimension [1, N, 2]
        point_labels = torch.from_numpy(batch_labels).unsqueeze(0)  # Add batch dimension [1, N]
        
        # Get predictions
        masks_batch, scores_batch, _ = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            multimask_output=False  # Get single best mask per point
        )
        
        # Convert tensors to numpy and add batch results to full list
        masks.extend([m.cpu().numpy() for m in masks_batch])
        scores.extend([s.mean().cpu().item() for s in scores_batch])
    
    segments = []
    total_area = image.shape[0] * image.shape[1]
    
    # Process each mask
    for i, (mask, score) in enumerate(zip(masks, scores)):
        if score < 0.5:  # Filter low confidence masks
            continue
            
        # Convert mask to uint8 (mask is already numpy array now)
        mask_uint8 = (mask > 0).astype(np.uint8) * 255
        
        # Find contours in the mask
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < total_area * 0.01:  # Skip tiny segments
                continue
                
            # Create mask for this contour
            contour_mask = np.zeros_like(mask_uint8)
            cv2.drawContours(contour_mask, [contour], -1, 255, -1)
            
            # Get mean color from the original image using this mask
            mean_color = cv2.mean(image, mask=contour_mask)[:3]
            
            # Simplify contour
            epsilon = 0.005 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Convert contour points to normalized coordinates
            points = []
            for point in approx:
                x = float(point[0][0]) / image.shape[1]
                y = float(point[0][1]) / image.shape[0]
                points.append({"x": x, "y": y})
            
            # Only add if we have enough points for a polygon
            if len(points) >= 3:
                segments.append({
                    "id": len(segments) + 1,
                    "color": rgb_to_hex(mean_color),
                    "area": float(area) / total_area,
                    "mask": points
                })
    
    logger.info("CV Service: Found {} segments", len(segments))
    return segments

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
        logger.info("CV Service: Running test segmentation with block-colors-01.jpg")
        
        if not TEST_IMAGE_PATH.exists():
            logger.error("CV Service: Test image not found at: {}", TEST_IMAGE_PATH)
            raise HTTPException(status_code=404, detail="Test image not found")
            
        # Read image using OpenCV
        image = cv2.imread(str(TEST_IMAGE_PATH))
        if image is None:
            raise HTTPException(status_code=400, detail="Failed to read test image")
        
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Find segments
        segments = find_contours(image)
        logger.info("CV Service: Found {} segments in test image", len(segments))
        
        # Extract dominant colors
        dominant_colors = get_dominant_colors(image_rgb)
        logger.info("CV Service: Extracted {} dominant colors from test image", len(dominant_colors))
        
        response = SegmentationResponse(
            message="Test segmentation completed",
            segments=segments,
            dominant_colors=dominant_colors
        )
        
        logger.info("CV Service: Sending test response")
        return response.dict()
        
    except Exception as e:
        logger.error("CV Service: Error during test segmentation: {}", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/segment")
async def segment_image(file_path: str):
    """Segment the image and extract dominant colors."""
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
        
        # Read image using OpenCV
        image = cv2.imread(str(image_path))
        if image is None:
            raise HTTPException(status_code=400, detail="Failed to read image")
        
        # Convert BGR to RGB for color processing
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Find segments
        segments = find_contours(image)
        logger.info("CV Service: Found {} segments", len(segments))
        
        # Extract dominant colors
        dominant_colors = get_dominant_colors(image_rgb)
        logger.info("CV Service: Extracted {} dominant colors", len(dominant_colors))
        
        # Create debug visualization
        debug_image_path = str(image_path).replace(".jpg", "_debug.jpg")
        create_debug_visualization(image, segments, debug_image_path)
        logger.info("CV Service: Created debug visualization at: {}", debug_image_path)
        
        response = SegmentationResponse(
            message="Segmentation completed",
            segments=segments,
            dominant_colors=dominant_colors,
            debug_image_path=os.path.basename(debug_image_path)
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
