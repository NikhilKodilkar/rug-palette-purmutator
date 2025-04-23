# Rug Permutator Testing Guide

## Connection Tests

The `test_connections.py` script verifies connectivity between all components of the system. It tests:

1. Frontend accessibility (port 5173)
2. API service health (port 3001)
3. CV service health (port 8000)
4. End-to-end image upload and segmentation flow

### Running the Tests

1. Start all services in separate terminals:

```bash
# Terminal 1 - CV Service
cd cv-service
python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0

# Terminal 2 - API Service
cd api
npm run dev

# Terminal 3 - Frontend
cd frontend
npm run dev
```

2. Run the connection tests:

```bash
python test_connections.py
```

### Test Results

The test will show:
- ✓ Green checkmarks for successful tests
- ✗ Red X's for failed tests
- Detailed error messages for failures
- A summary of total passed/failed tests

### What's Being Tested

1. **Frontend Test**
   - Verifies the Vite dev server is running
   - Checks if the frontend is accessible on port 5173

2. **API Health Check**
   - Verifies the Express server is running
   - Checks if the health endpoint returns status "OK"
   - Confirms media directory is properly configured

3. **CV Service Health Check**
   - Verifies the FastAPI server is running
   - Checks if the health endpoint returns status "OK"
   - Confirms media path configuration

4. **End-to-End Test**
   - Uploads a test image through the API
   - Verifies the API can forward requests to CV service
   - Checks if segmentation results are returned
   - Validates the response format

### Common Issues

1. **Connection Refused**
   - Check if all services are running
   - Verify the ports are correct and not in use
   - Ensure IPv4 addresses are used (127.0.0.1 instead of localhost)

2. **Media Path Issues**
   - Verify the media directory exists in both API and CV service
   - Check the .env files have correct MEDIA_PATH settings
   - Ensure file permissions are correct

3. **Image Not Found**
   - Check if test images exist in test_assets directory
   - Verify media path synchronization between services
   - Check file permissions

### Running Tests in CI/CD

The test script exits with:
- Code 0 if all tests pass
- Code 1 if any test fails

This makes it suitable for integration into CI/CD pipelines. 