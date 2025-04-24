import React, { useState, useRef } from 'react';
import FileUpload from './components/FileUpload';
import './App.css';

interface Point {
  x: number;
  y: number;
}

interface Segment {
  id: number;
  color: string;
  area: number;  // Normalized area (0-1)
  mask: Point[];
  pixelArea?: number;  // Actual pixel area
}

interface UploadResponse {
  message: string;
  filename: string;
  path: string;
  segments: Segment[];
  dominant_colors: string[];
}

interface TooltipPosition {
  x: number;
  y: number;
}

const DeleteIcon = () => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    viewBox="0 0 24 24"
    width="16" 
    height="16"
    fill="currentColor"
  >
    <path d="M21,4h-3.1c-0.5-2.3-2.5-4-4.9-4S8.6,1.7,8.1,4H5C4.4,4,4,4.4,4,5s0.4,1,1,1h1v13c0,2.2,1.8,4,4,4h6c2.2,0,4-1.8,4-4V6h1
      c0.6,0,1-0.4,1-1S21.6,4,21,4z M13,2c1.3,0,2.4,0.8,2.8,2h-5.6C10.6,2.8,11.7,2,13,2z M17,19c0,1.1-0.9,2-2,2H9c-1.1,0-2-0.9-2-2V6
      h10V19z"/>
    <path d="M9,17c0.6,0,1-0.4,1-1V9c0-0.6-0.4-1-1-1S8,8.4,8,9v7C8,16.6,8.4,17,9,17z"/>
    <path d="M15,17c0.6,0,1-0.4,1-1V9c0-0.6-0.4-1-1-1s-1,0.4-1,1v7C14,16.6,14.4,17,15,17z"/>
  </svg>
);

function App() {
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [hoveredSegment, setHoveredSegment] = useState<number | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition | null>(null);
  const [removedSegments, setRemovedSegments] = useState<Set<number>>(new Set());
  const [segmentToDelete, setSegmentToDelete] = useState<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);

  const handleUploadSuccess = (responseData: UploadResponse) => {
    console.log('[Frontend] Raw data received from backend:', responseData);
    console.log('[Frontend] Processing data for display:', {
      filename: responseData.filename,
      segmentsCount: responseData.segments.length,
      dominantColorsCount: responseData.dominant_colors.length
    });
    
    setUploadResult(responseData);
    setRemovedSegments(new Set()); // Reset removed segments on new upload
    console.log('[Frontend] Data set for display, rendering will begin');
  };

  const handleUploadError = (errorMessage: string) => {
    console.error('[Frontend] Upload failed:', errorMessage);
    alert(`Upload failed: ${errorMessage}`);
    setUploadResult(null);
    setRemovedSegments(new Set());
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
    setImageSize({ width: img.width, height: img.height });

    // Draw original image
    ctx.drawImage(img, 0, 0);

    // Draw each segment with its color (no hover effect here)
    segments
      .filter(segment => !removedSegments.has(segment.id))
      .forEach(segment => {
        if (segment.mask.length < 3) return;

        ctx.beginPath();
        ctx.moveTo(
          segment.mask[0].x * canvas.width,
          segment.mask[0].y * canvas.height
        );
        
        for (let i = 1; i < segment.mask.length; i++) {
          ctx.lineTo(
            segment.mask[i].x * canvas.width,
            segment.mask[i].y * canvas.height
          );
        }
        
        ctx.closePath();

        // Fill with semi-transparent color
        ctx.fillStyle = segment.color + '80'; // 50% opacity
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

    // Find segment under cursor (excluding removed segments)
    const segment = uploadResult.segments.find(segment => 
      !removedSegments.has(segment.id) && isPointInPolygon({ x, y }, segment.mask)
    );

    setHoveredSegment(segment?.id ?? null);
    
    if (segment) {
      setTooltipPosition({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      });
    } else {
      setTooltipPosition(null);
    }
  };

  const handleCanvasMouseLeave = () => {
    setHoveredSegment(null);
    setTooltipPosition(null);
  };

  const handleDeleteSegment = (segmentId: number) => {
    setSegmentToDelete(segmentId);
  };

  const confirmDelete = () => {
    if (segmentToDelete !== null && uploadResult) {
      const newRemovedSegments = new Set(removedSegments);
      newRemovedSegments.add(segmentToDelete);
      setRemovedSegments(newRemovedSegments);

      // Redraw canvas
      const img = new Image();
      img.onload = () => {
        if (canvasRef.current) {
          drawSegments(canvasRef.current, img, uploadResult.segments);
        }
      };
      img.src = `http://localhost:3001/media/${uploadResult.filename}`;
      
      setSegmentToDelete(null);
    }
  };

  const cancelDelete = () => {
    setSegmentToDelete(null);
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
                      canvasRef.current = canvas;
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
                  {imageSize && hoveredSegment && (
                    <svg
                      className="segment-highlight active"
                      style={{
                        width: '100%',
                        height: '100%',
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        pointerEvents: 'none'
                      }}
                      viewBox={`0 0 ${imageSize.width} ${imageSize.height}`}
                      preserveAspectRatio="none"
                    >
                      {uploadResult?.segments
                        .filter(s => s.id === hoveredSegment && !removedSegments.has(s.id))
                        .map(segment => (
                          <path
                            key={segment.id}
                            d={`M ${segment.mask.map(p => 
                              `${p.x * imageSize.width},${p.y * imageSize.height}`
                            ).join(' L ')} Z`}
                          />
                        ))}
                    </svg>
                  )}
                </div>
              </div>
            </div>
            
            <h3>Segments</h3>
            <div className="segment-list">
              {uploadResult.segments
                .filter(segment => !removedSegments.has(segment.id))
                .map((segment) => (
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
                  <button 
                    className="delete-button"
                    onClick={() => handleDeleteSegment(segment.id)}
                    title="Remove segment"
                  >
                    <DeleteIcon />
                  </button>
                </div>
              ))}
            </div>

            {segmentToDelete !== null && (
              <div className="modal-overlay">
                <div className="modal-content">
                  <h4>Confirm Deletion</h4>
                  <p>Are you sure you want to remove segment {segmentToDelete}?</p>
                  <div className="modal-actions">
                    <button onClick={confirmDelete}>Yes, remove</button>
                    <button onClick={cancelDelete}>Cancel</button>
                  </div>
                </div>
              </div>
            )}

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
