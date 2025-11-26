from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import uvicorn
from typing import List, Dict
import mimetypes
from pydantic import BaseModel
import shutil
import hashlib
from PIL import Image
import tempfile

app = FastAPI()

# Mount frontend directory to serve static files (css, js if any)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")

# Thumbnail cache directory
THUMBNAIL_CACHE_DIR = os.path.join(tempfile.gettempdir(), "image_viewer_thumbnails")
os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# --- Config & Models ---

class ShortcutConfig(BaseModel):
    next: str = "ArrowDown"
    prev: str = "ArrowUp"
    clear: str = "c"
    # Map key -> class name
    classes: Dict[str, str] = {
        "1": "zhengbao",
        "2": "wubao"
    }
    # Map class name -> hex color
    class_colors: Dict[str, str] = {
        "1": "#28a745",
        "2": "#dc3545",
        "3": "#007bff",
        "4": "#fd7e14",
        "5": "#6f42c1"
    }

class AppConfig(BaseModel):
    shortcuts: ShortcutConfig = ShortcutConfig()

# In-memory config for now (could be saved to file)
current_config = AppConfig()

class ClassifyRequest(BaseModel):
    image_path: str
    class_name: str

# --- Endpoints ---

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/api/config")
async def get_config():
    return current_config

@app.post("/api/config")
async def update_config(config: AppConfig):
    global current_config
    current_config = config
    return current_config

@app.post("/api/classify")
async def classify_image(req: ClassifyRequest):
    if not os.path.exists(req.image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Determine target directory
    # Strategy: Create a sibling directory to the image's parent directory with the class name
    image_dir = os.path.dirname(req.image_path)
    # If image_dir is root of drive, this might be weird, but assuming normal folders
    # If user wants specific paths, we might need more complex config. 
    # Current requirement: "if no .../1 folder, create it". Implies sibling or child.
    # "when image path is /.../test_images, click 1 ... check /.../1"
    # This implies sibling directory.
    
    parent_dir = os.path.dirname(image_dir)
    target_dir = os.path.join(parent_dir, req.class_name)
    filename = os.path.basename(req.image_path)
    
    # IMPORTANT: Remove image from ALL other classification folders first
    # This ensures exclusive classification - image can only be in one class at a time
    if os.path.exists(parent_dir):
        for entry in os.scandir(parent_dir):
            if entry.is_dir() and entry.name != req.class_name and entry.name != os.path.basename(image_dir):
                # Check if this image exists in this class folder
                potential_old_path = os.path.join(entry.path, filename)
                if os.path.exists(potential_old_path):
                    try:
                        os.remove(potential_old_path)
                    except Exception as e:
                        # Log but don't fail - we still want to proceed with new classification
                        print(f"Warning: Failed to remove old classification: {e}")
    
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed to create directory: {e}")

    target_path = os.path.join(target_dir, filename)

    try:
        shutil.copy2(req.image_path, target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy image: {e}")

    return {"status": "success", "target_path": target_path, "class_name": req.class_name}

@app.post("/api/unclassify")
async def unclassify_image(req: ClassifyRequest):
    # Remove the copy from the class folder
    # We need to know where it was copied. 
    # Re-calculate target path based on class name.
    
    image_dir = os.path.dirname(req.image_path)
    parent_dir = os.path.dirname(image_dir)
    target_dir = os.path.join(parent_dir, req.class_name)
    filename = os.path.basename(req.image_path)
    target_path = os.path.join(target_dir, filename)
    
    if os.path.exists(target_path):
        try:
            os.remove(target_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")
            
    return {"status": "success", "detail": "Classification removed"}

@app.get("/api/images")
async def list_images(path: str = Query(..., description="Directory path to list images from")):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Directory not found")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
    images = []
    try:
        for entry in os.scandir(path):
            if entry.is_file() and os.path.splitext(entry.name)[1].lower() in image_extensions:
                images.append(entry.name)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Sort descending by filename
    images.sort(key=lambda x: x.lower(), reverse=True)
    
    # Detect historical classifications by scanning sibling directories
    classifications = {}
    parent_dir = os.path.dirname(path)
    
    if os.path.exists(parent_dir):
        try:
            for entry in os.scandir(parent_dir):
                # Skip the source directory itself
                if entry.is_dir() and entry.path != path:
                    # This could be a classification folder
                    class_name = entry.name
                    # Check which images exist in this potential classification folder
                    for image_filename in images:
                        classified_image_path = os.path.join(entry.path, image_filename)
                        if os.path.exists(classified_image_path):
                            # This image has been classified to this class
                            classifications[image_filename] = class_name
        except PermissionError:
            # If we can't read parent directory, just skip classification detection
            pass
    
    return {"images": images, "path": path, "classifications": classifications}

@app.get("/api/image")
async def get_image(path: str = Query(..., description="Full path to the image file")):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Security check: ensure it's actually a file
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail="Not a file")

    # Basic check for image extension
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
    if os.path.splitext(path)[1].lower() not in image_extensions:
         raise HTTPException(status_code=400, detail="Not an image file")

    return FileResponse(path)

def generate_cache_key(file_path: str, size: int) -> str:
    """Generate a unique cache key based on file path, modification time, and thumbnail size."""
    try:
        mtime = os.path.getmtime(file_path)
        cache_input = f"{file_path}_{mtime}_{size}"
        return hashlib.md5(cache_input.encode()).hexdigest()
    except:
        return hashlib.md5(file_path.encode()).hexdigest()

@app.get("/api/thumbnail")
async def get_thumbnail(
    path: str = Query(..., description="Full path to the image file"),
    size: int = Query(300, description="Thumbnail size (max width/height)")
):
    """Generate and cache thumbnails for fast grid loading."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail="Not a file")

    # Check if it's an image
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
    if os.path.splitext(path)[1].lower() not in image_extensions:
        raise HTTPException(status_code=400, detail="Not an image file")

    # Generate cache key
    cache_key = generate_cache_key(path, size)
    thumbnail_path = os.path.join(THUMBNAIL_CACHE_DIR, f"{cache_key}.jpg")

    # Return cached thumbnail if it exists
    if os.path.exists(thumbnail_path):
        return FileResponse(thumbnail_path, media_type="image/jpeg")

    # Generate thumbnail
    try:
        with Image.open(path) as img:
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Create thumbnail
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Save with optimization
            img.save(thumbnail_path, "JPEG", quality=85, optimize=True)
        
        return FileResponse(thumbnail_path, media_type="image/jpeg")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail: {str(e)}")

@app.delete("/api/thumbnails")
async def clear_thumbnails():
    """Clear all cached thumbnails."""
    try:
        deleted_count = 0
        if os.path.exists(THUMBNAIL_CACHE_DIR):
            for filename in os.listdir(THUMBNAIL_CACHE_DIR):
                file_path = os.path.join(THUMBNAIL_CACHE_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
        return {"status": "success", "deleted": deleted_count, "message": f"Cleared {deleted_count} thumbnails"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear thumbnails: {str(e)}")

@app.get("/api/thumbnail-stats")
async def get_thumbnail_stats():
    """Get statistics about the thumbnail cache."""
    try:
        count = 0
        total_size = 0
        if os.path.exists(THUMBNAIL_CACHE_DIR):
            for filename in os.listdir(THUMBNAIL_CACHE_DIR):
                file_path = os.path.join(THUMBNAIL_CACHE_DIR, filename)
                if os.path.isfile(file_path):
                    count += 1
                    total_size += os.path.getsize(file_path)
        
        return {
            "cache_dir": THUMBNAIL_CACHE_DIR,
            "count": count,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
