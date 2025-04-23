import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import './App.css';

interface Point {
  x: number;
  y: number;
}

interface Segment {
  id: number;
  color: string;
  area: number;
  mask: Point[];
}

interface UploadResponse {
  message: string;
  filename: string;
  path: string;
  segments: Segment[];
  dominant_colors: string[];
}

function App() {
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  const handleUploadSuccess = (responseData: UploadResponse) => {
    console.log('[Frontend] Raw data received from backend:', responseData);
    console.log('[Frontend] Processing data for display:', {
      filename: responseData.filename,
      segmentsCount: responseData.segments.length,
      dominantColorsCount: responseData.dominant_colors.length
    });
    
    setUploadResult(responseData);
    console.log('[Frontend] Data set for display, rendering will begin');
  };

  const handleUploadError = (errorMessage: string) => {
    console.error('[Frontend] Upload failed:', errorMessage);
    alert(`Upload failed: ${errorMessage}`);
    setUploadResult(null);
  };

  // Add effect to log when display is complete
  React.useEffect(() => {
    if (uploadResult) {
      console.log('[Frontend] Display completed successfully');
    }
  }, [uploadResult]);

  const drawSegments = (canvas: HTMLCanvasElement, img: HTMLImageElement, segments: Segment[]) => {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size to match image
    canvas.width = img.width;
    canvas.height = img.height;

    // Draw original image
    ctx.drawImage(img, 0, 0);

    // Draw each segment as a polygon with semi-transparent fill
    segments.forEach(segment => {
      if (segment.mask.length < 3) return; // Need at least 3 points for a polygon

      ctx.beginPath();
      // Move to first point
      ctx.moveTo(
        segment.mask[0].x * canvas.width,
        segment.mask[0].y * canvas.height
      );
      
      // Draw lines to subsequent points
      for (let i = 1; i < segment.mask.length; i++) {
        ctx.lineTo(
          segment.mask[i].x * canvas.width,
          segment.mask[i].y * canvas.height
        );
      }
      
      // Close the path
      ctx.closePath();

      // Fill with semi-transparent color
      ctx.fillStyle = segment.color + '80'; // Add 50% transparency
      ctx.fill();

      // Draw border
      ctx.strokeStyle = segment.color;
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Rug Palette Permutator</h1>
      </header>
      <main>
        <FileUpload
          onUploadSuccess={handleUploadSuccess}
          onUploadError={handleUploadError}
        />
        {uploadResult && (
          <div className="results-container">
            <h2>Segmentation Results</h2>
            <div className="image-container">
              <div className="original-image">
                <h3>Original Image</h3>
                <img 
                  src={`http://localhost:3001/media/${uploadResult.filename}`} 
                  alt="Original rug" 
                  className="rug-image"
                />
              </div>
              <div className="segmented-view">
                <h3>Segmented View</h3>
                <div className="segmented-image">
                  <canvas
                    ref={(canvas) => {
                      if (canvas && uploadResult) {
                        const img = new Image();
                        img.onload = () => {
                          drawSegments(canvas, img, uploadResult.segments);
                        };
                        img.src = `http://localhost:3001/media/${uploadResult.filename}`;
                      }
                    }}
                    className="rug-image"
                  />
                </div>
              </div>
            </div>
            <div className="segments">
              <h3>Segments</h3>
              <div className="segment-list">
                {uploadResult.segments.map((segment) => (
                  <div key={segment.id} className="segment-item">
                    <div 
                      className="color-preview" 
                      style={{ backgroundColor: segment.color }}
                    />
                    <span>Area: {(segment.area * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="dominant-colors">
              <h3>Dominant Colors</h3>
              <div className="color-list">
                {uploadResult.dominant_colors.map((color, index) => (
                  <div key={index} className="color-item">
                    <div 
                      className="color-preview" 
                      style={{ backgroundColor: color }}
                    />
                    <span>{color}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
