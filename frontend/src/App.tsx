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
  const [hoveredSegment, setHoveredSegment] = useState<number | null>(null);

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

      // Fill with semi-transparent color, darker if hovered
      const alpha = hoveredSegment === segment.id ? 'B0' : '80'; // 70% or 50% opacity
      ctx.fillStyle = segment.color + alpha;
      ctx.fill();

      // Draw border
      ctx.strokeStyle = segment.color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Add segment ID text
      const centroid = segment.mask.reduce(
        (acc, point) => ({
          x: acc.x + point.x / segment.mask.length,
          y: acc.y + point.y / segment.mask.length
        }),
        { x: 0, y: 0 }
      );

      ctx.fillStyle = 'white';
      ctx.strokeStyle = 'black';
      ctx.lineWidth = 3;
      ctx.font = '16px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const text = segment.id.toString();
      const x = centroid.x * canvas.width;
      const y = centroid.y * canvas.height;
      
      // Draw text with outline for better visibility
      ctx.strokeText(text, x, y);
      ctx.fillText(text, x, y);
    });
  };

  const handleCanvasMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!uploadResult) return;

    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / canvas.clientWidth;
    const y = (event.clientY - rect.top) / canvas.clientHeight;

    // Find segment under cursor
    const hoveredSegment = uploadResult.segments.find(segment => {
      return isPointInPolygon({ x, y }, segment.mask);
    });

    setHoveredSegment(hoveredSegment?.id ?? null);
  };

  const handleCanvasMouseLeave = () => {
    setHoveredSegment(null);
  };

  // Helper function to check if a point is inside a polygon
  const isPointInPolygon = (point: Point, polygon: Point[]): boolean => {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i].x, yi = polygon[i].y;
      const xj = polygon[j].x, yj = polygon[j].y;
      
      const intersect = ((yi > point.y) !== (yj > point.y))
          && (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
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
                    onMouseMove={handleCanvasMouseMove}
                    onMouseLeave={handleCanvasMouseLeave}
                    className="rug-image"
                  />
                </div>
              </div>
            </div>
            
            <h3>Segments</h3>
            <div className="segment-list">
              {uploadResult.segments.map((segment) => (
                <div 
                  key={segment.id} 
                  className={`segment-item ${hoveredSegment === segment.id ? 'hovered' : ''}`}
                  onMouseEnter={() => setHoveredSegment(segment.id)}
                  onMouseLeave={() => setHoveredSegment(null)}
                >
                  <div 
                    className="color-preview" 
                    style={{ backgroundColor: segment.color }}
                  />
                  <span>ID: {segment.id}</span>
                  <span>Area: {(segment.area * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
            <div className="dominant-colors">
              <h3>Dominant Colors ({uploadResult.dominant_colors.length}) - {uploadResult.segments.length} segments found</h3>
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
