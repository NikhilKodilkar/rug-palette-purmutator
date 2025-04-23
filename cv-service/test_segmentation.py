import cv2
import numpy as np
import torch
from pathlib import Path
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
from loguru import logger
import time
import traceback

def test_segmentation():
    # Setup paths
    base_dir = Path(__file__).parent
    project_root = base_dir.parent
    test_image_path = project_root / "block-colors-01.jpg"
    checkpoint_path = base_dir / "models" / "sam_vit_h_4b8939.pth"

    logger.info(f"Base directory: {base_dir}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Looking for image at: {test_image_path}")
    logger.info(f"Looking for checkpoint at: {checkpoint_path}")

    if not test_image_path.exists():
        raise FileNotFoundError(f"Test image not found at {test_image_path}")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"SAM model checkpoint not found at {checkpoint_path}")

    # Initialize SAM model
    logger.info("Initializing SAM model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    sam = sam_model_registry["vit_h"](checkpoint=str(checkpoint_path))
    sam.to(device=device)
    logger.info("SAM model initialized successfully")

    # Initialize Automatic Mask Generator
    mask_generator = SamAutomaticMaskGenerator(
        model=sam,
        points_per_side=32,
        pred_iou_thresh=0.88,
        stability_score_thresh=0.95,
        min_mask_region_area=100
    )
    logger.info("SamAutomaticMaskGenerator initialized")

    # Read test image
    logger.info(f"Reading test image from {test_image_path}")
    image = cv2.imread(str(test_image_path))
    if image is None:
        raise ValueError(f"Failed to read test image at {test_image_path}")

    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    logger.info(f"Image loaded - shape: {image_rgb.shape}, dtype: {image_rgb.dtype}")
    h, w = image.shape[:2]

    # Generate masks automatically
    logger.info("Starting automatic mask generation...")
    start_time = time.time()
    masks_data = mask_generator.generate(image_rgb)
    end_time = time.time()
    logger.info(f"Automatic mask generation finished in {end_time - start_time:.2f} seconds")
    logger.info(f"Generated {len(masks_data)} raw masks")

    # Process the generated masks
    final_masks = []
    final_scores = []

    for i, mask_info in enumerate(masks_data):
        mask = mask_info['segmentation']
        score = mask_info['predicted_iou']
        area = mask_info['area']

        # Filter by relative area
        min_relative_area = 0.01  # Require segment to be at least 1% of the image
        if area < h * w * min_relative_area:
            continue

        logger.info(f"Processing generated segment {i}: Area={area}, Predicted IoU={score:.3f}")
        final_masks.append(mask)
        final_scores.append(score)

    logger.info(f"Found {len(final_masks)} segments after filtering")
    return final_masks, final_scores, image

if __name__ == "__main__":
    logger.info("Starting test using SamAutomaticMaskGenerator...")
    try:
        masks, scores, original_image = test_segmentation()
        logger.info("Test completed successfully")
        logger.info(f"Found {len(masks)} final segments")

        # Create output directory for individual segments
        base_dir = Path(__file__).parent
        segments_dir = base_dir / "segments"
        segments_dir.mkdir(exist_ok=True)

        # Log first few segment scores for confirmation
        sorted_results = sorted(zip(scores, masks), key=lambda x: x[0], reverse=True)
        for i in range(min(len(sorted_results), 15)):
            score, mask = sorted_results[i]
            logger.info(f"Segment {i+1}: score {score:.3f}, Area (pixels) {np.sum(mask)}")
        if len(scores) > 15:
            logger.info("...")

        # Create a composite visualization
        if masks:
            composite_image = original_image.copy()
            for i, (score, mask) in enumerate(sorted_results):
                # Generate a random color for each mask
                color = np.random.randint(0, 255, size=3, dtype=np.uint8)
                
                # Save individual segment
                segment_image = original_image.copy()
                segment_image[~mask] = 0  # Set non-mask area to black
                segment_path = segments_dir / f"segment_{i+1}_score_{score:.3f}.jpg"
                cv2.imwrite(str(segment_path), segment_image)
                logger.info(f"Saved segment {i+1} to {segment_path}")

                # Apply mask to composite visualization
                rows, cols = np.where(mask)
                composite_image[rows, cols] = (composite_image[rows, cols] * 0.5 + color * 0.5).astype(np.uint8)
                
                # Add segment ID and score
                center = (int(np.mean(cols)), int(np.mean(rows)))
                cv2.putText(composite_image, f"{i+1}", center, 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            # Save composite visualization
            composite_path = base_dir / "composite_segmentation.jpg"
            cv2.imwrite(str(composite_path), composite_image)
            logger.info(f"Saved composite segmentation visualization to {composite_path}")

    except FileNotFoundError as e:
        logger.error(f"Test failed: Required file not found. {str(e)}")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        logger.error(traceback.format_exc()) 