import React, { useCallback, useState } from 'react';
import { useDropzone, Accept } from 'react-dropzone';

interface FileUploadProps {
  onUploadSuccess: (responseData: any) => void;
  onUploadError: (errorMessage: string) => void;
}

const acceptedImageTypes: Accept = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
};

function FileUpload({ onUploadSuccess, onUploadError }: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) {
      const msg = "No valid files selected.";
      console.error(msg);
      setError(msg);
      return;
    }

    const file = acceptedFiles[0];
    console.log('Starting upload for file:', {
      name: file.name,
      type: file.type,
      size: file.size
    });
    
    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('rugImage', file);

    try {
      console.log('[Frontend] Sending request to API...');
      const response = await fetch('http://localhost:3001/upload', {
        method: 'POST',
        body: formData,
      });

      console.log('Received response:', {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries())
      });

      const data = await response.json();
      console.log('Response data:', data);

      if (!response.ok) {
        throw new Error(data.message || `Upload failed: ${response.status}`);
      }

      console.log('Upload successful:', data);
      onUploadSuccess(data);
    } catch (err) {
      console.error('Upload error details:', err);
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
      onUploadError(message);
    } finally {
      setIsUploading(false);
    }
  }, [onUploadSuccess, onUploadError]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: acceptedImageTypes,
    multiple: false,
    maxSize: 10 * 1024 * 1024,
  });

  return (
    <div className="file-upload-container">
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
        <input {...getInputProps()} />
        {isUploading ? (
          <p>Uploading...</p>
        ) : isDragActive ? (
          <p>Drop the image here ...</p>
        ) : (
          <p>Drag 'n' drop a rug image here, or click to select</p>
        )}
      </div>
      {error && <p className="error-message">{error}</p>}
    </div>
  );
}

export default FileUpload;
