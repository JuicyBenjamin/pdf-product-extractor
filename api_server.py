from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import shutil
from pathlib import Path
import zipfile
import io

from extract_final_v2 import FinalProductExtractor

app = FastAPI(title="PDF Product Extractor API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface"""
    html_path = Path(__file__).parent / "web_interface.html"
    if html_path.exists():
        with open(html_path, 'r') as f:
            return f.read()
    return HTMLResponse(content="<h1>PDF Product Extractor API</h1><p>Upload endpoint: POST /extract/download</p>")


@app.post("/extract/download")
async def extract_and_download(file: UploadFile = File(...)):
    """
    Extract product images and return as ZIP file.
    """
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    # Create temporary directory
    temp_dir_obj = tempfile.mkdtemp()
    temp_dir = Path(temp_dir_obj)
    
    try:
        # Save uploaded PDF
        pdf_path = temp_dir / file.filename
        with open(pdf_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Extract
        output_dir = temp_dir / "output"
        extractor = FinalProductExtractor(str(pdf_path), str(output_dir))
        result = extractor.process()
        extractor.close()
        
        # Create ZIP of output
        zip_path = temp_dir / "extraction.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from output directory
            for file_path in output_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(output_dir)
                    zipf.write(file_path, arcname)
        
        # Return ZIP file
        return FileResponse(
            path=str(zip_path),
            media_type='application/zip',
            filename=f"{extractor.product_name}.zip",
            background=None
        )
        
    except Exception as e:
        # Clean up on error
        shutil.rmtree(temp_dir_obj, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint with tesseract verification"""
    import subprocess
    import shutil
    
    # Check if tesseract is available
    tesseract_path = shutil.which("tesseract")
    tesseract_installed = tesseract_path is not None
    
    tesseract_version = None
    if tesseract_installed:
        try:
            result = subprocess.run(["tesseract", "--version"], 
                                  capture_output=True, text=True)
            tesseract_version = result.stdout.split('\n')[0]
        except:
            pass
    
    return {
        "status": "healthy",
        "tesseract_installed": tesseract_installed,
        "tesseract_path": tesseract_path,
        "tesseract_version": tesseract_version
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
