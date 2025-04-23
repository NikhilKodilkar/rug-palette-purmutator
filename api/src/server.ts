    // api/src/server.ts
    import express, { Request, Response, NextFunction } from 'express';
    import multer from 'multer';
    import path from 'path';
    import fs from 'fs';
    import crypto from 'crypto';
    import cors from 'cors';
    import dotenv from 'dotenv';
    import { fileURLToPath } from 'url'; // Helper for __dirname in ES modules
    import fetch from 'node-fetch';

    interface Segment {
      id: number;
      color: string;
      area: number;
    }

    interface SegmentationResponse {
      message: string;
      segments: Segment[];
      dominant_colors: string[];
    }

    dotenv.config(); // Load .env file

    const app = express();
    const port = process.env.PORT || 3001;  // Consistently use 3001 as default
    const CV_SERVICE_URL = process.env.CV_SERVICE_URL || 'http://localhost:8000';

    // Determine __dirname equivalent in ES module scope
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);

    // --- File Storage Configuration ---
    const mediaPath = process.env.MEDIA_PATH || path.join(__dirname, '..', 'media'); // Default if not set

    // Ensure the media directory exists (important for Docker volume mapping)
    if (!fs.existsSync(mediaPath)) {
        console.log(`[API] Creating media directory: ${mediaPath}`);
        fs.mkdirSync(mediaPath, { recursive: true });
    } else {
        console.log(`[API] Media directory exists: ${mediaPath}`);
        console.log(`[API] Media directory contents:`, fs.readdirSync(mediaPath));
    }

    // Log all environment variables
    console.log('[API] Environment:', {
        NODE_ENV: process.env.NODE_ENV,
        PORT: port,
        CV_SERVICE_URL,
        MEDIA_PATH: mediaPath
    });

    // --- CORS Configuration ---
    // TODO: Restrict this in production!
    const corsOptions = {
      origin: '*', // Allow all origins for now (adjust for frontend URL in prod)
      methods: 'GET,HEAD,PUT,PATCH,POST,DELETE',
      credentials: true,
    };
    app.use(cors(corsOptions));

    // Serve media files
    app.use('/media', express.static(mediaPath));

    const storage = multer.diskStorage({
      destination: function (req, file, cb) {
        console.log('Multer processing file:', {
          originalname: file.originalname,
          mimetype: file.mimetype,
          size: file.size
        });
        cb(null, mediaPath); // Save files to the configured media path
      },
      filename: function (req, file, cb) {
        // Generate a unique filename (e.g., timestamp-random-original.ext)
        const uniqueSuffix = Date.now() + '-' + crypto.randomBytes(6).toString('hex');
        const extension = path.extname(file.originalname);
        const filename = file.fieldname + '-' + uniqueSuffix + extension;
        console.log('Generated filename:', filename);
        cb(null, filename);
      }
    });

    // --- Multer Filter (Optional: add more checks if needed) ---
    const fileFilter = (req: Request, file: Express.Multer.File, cb: multer.FileFilterCallback) => {
        console.log('Checking file:', {
            fieldname: file.fieldname,
            originalname: file.originalname,
            mimetype: file.mimetype
        });
        
        if (file.mimetype.startsWith('image/')) {
            console.log('File accepted: Valid image type');
            cb(null, true);
        } else {
             console.log(`File rejected: Invalid mime type - ${file.mimetype}`);
             cb(null, false); // Reject file
             // Optionally, pass an error: cb(new Error('Only image files are allowed!'))
        }
    };

    const upload = multer({
        storage: storage,
        limits: { fileSize: 10 * 1024 * 1024 }, // 10MB limit matches frontend
        fileFilter: fileFilter
    });


    // --- Routes ---
    app.get('/health', (req: Request, res: Response) => {
        res.status(200).json({ status: 'API is running' });
    });

    app.post('/upload', upload.single('rugImage'), async (req: Request, res: Response) => {
      console.log('[API] Received upload request');
      
      try {
        if (!req.file) {
          console.log('[API] Upload attempt failed: No file received or file rejected by filter.');
          return res.status(400).json({ 
            message: 'Upload failed. Make sure it is an image file (JPG, PNG, WEBP) under 10MB.' 
          });
        }

        console.log('[API] File uploaded successfully:', {
          filename: req.file.filename,
          path: req.file.path,
          size: req.file.size,
          mimetype: req.file.mimetype
        });

        // Trigger segmentation
        try {
          console.log('[API] Sending request to CV service for segmentation:', {
            url: `${CV_SERVICE_URL}/segment?file_path=${req.file.filename}`,
            method: 'POST'
          });

          const segmentResponse = await fetch(`${CV_SERVICE_URL}/segment?file_path=${req.file.filename}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            }
          });

          console.log('[API] CV service response status:', segmentResponse.status);

          if (!segmentResponse.ok) {
            const errorText = await segmentResponse.text();
            console.error('[API] CV service error:', {
              status: segmentResponse.status,
              statusText: segmentResponse.statusText,
              error: errorText
            });
            throw new Error(`Segmentation failed: ${errorText}`);
          }

          const segmentData = await segmentResponse.json() as SegmentationResponse;
          console.log('[API] Raw CV service response:', JSON.stringify(segmentData, null, 2));
          
          // Validate the response data
          if (!Array.isArray(segmentData.segments) || !Array.isArray(segmentData.dominant_colors)) {
            console.error('[API] Invalid CV service response:', segmentData);
            throw new Error('Invalid response from CV service: segments or dominant_colors are not arrays');
          }

          console.log('[API] Segmentation successful:', {
            filename: req.file.filename,
            segments: segmentData.segments.length,
            dominantColors: segmentData.dominant_colors.length
          });

          console.log('[API] Sending response to frontend');
          res.status(201).json({
            message: 'File uploaded and segmented successfully!',
            filename: req.file.filename,
            path: req.file.path,
            segments: segmentData.segments,
            dominant_colors: segmentData.dominant_colors
          });

        } catch (segmentError) {
          console.error('[API] Segmentation error:', segmentError);
          res.status(500).json({
            message: 'File uploaded but segmentation failed',
            error: segmentError instanceof Error ? segmentError.message : 'Unknown error',
            filename: req.file.filename
          });
        }

      } catch (error) {
        console.error('[API] Upload handler error:', error);
        res.status(500).json({
          message: 'Server error during upload',
          error: error instanceof Error ? error.message : 'Unknown error'
        });
      }
    });


    // --- Global Error Handler ---
    app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
      console.error('Unhandled Error:', err.stack);
       // Handle Multer errors specifically if needed
       if (err instanceof multer.MulterError) {
            if (err.code === 'LIMIT_FILE_SIZE') {
               return res.status(400).json({ message: 'File is too large. Maximum size is 10MB.' });
            }
            // Handle other Multer errors
             return res.status(400).json({ message: `File upload error: ${err.message}` });
       }

      res.status(500).json({ message: 'Something went wrong on the server!' });
    });


    // --- Start Server ---
    app.listen(port, () => {
      console.log(`API server listening on port ${port}`);
      console.log(`Media path configured to: ${mediaPath}`);
    });
