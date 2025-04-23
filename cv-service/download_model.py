import urllib.request
import os
from pathlib import Path

def download_sam_model():
    # Create models directory if it doesn't exist
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    
    # Model URL and destination path
    url = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
    model_path = models_dir / "sam_vit_h_4b8939.pth"
    
    print(f"Downloading SAM model to {model_path}...")
    urllib.request.urlretrieve(url, model_path)
    print("Download complete!")

if __name__ == "__main__":
    download_sam_model() 