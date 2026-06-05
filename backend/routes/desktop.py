import os
import json
import tempfile
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/desktop", tags=["desktop"])

class DesktopConfigPayload(BaseModel):
    schemaVersion: int
    runtime: dict
    backend: dict
    ai: dict

@router.get("/config")
def get_config():
    if os.environ.get("DESKTOP_MODE", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Desktop mode is not enabled.")
        
    config_path = os.environ.get("CONFIG_PATH")
    if not config_path or not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Config file not found or CONFIG_PATH not set.")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {str(e)}")

def _validate_config(config: dict):
    errors = []
    warnings = []
    
    try:
        runtime = config.get("runtime", {})
        base_dir = runtime.get("baseDir", "")
        actors_dir = runtime.get("actorsDir", "")
        models_dir = runtime.get("modelsDir", "")
        faiss_index_dir = runtime.get("faissIndexDir", "")
        videos_dir = runtime.get("videosDir", "")
        jobs_dir = runtime.get("jobsDir", "")
        logs_dir = runtime.get("logsDir", "")
        
        if not base_dir or not os.path.isdir(base_dir):
            errors.append(f"Base directory not found: {base_dir}")
        if not actors_dir or not os.path.isdir(actors_dir):
            errors.append(f"Actors directory not found: {actors_dir}")
        if not models_dir or not os.path.isdir(models_dir):
            errors.append(f"Models directory not found: {models_dir}")
        if not faiss_index_dir or not os.path.isdir(faiss_index_dir):
            errors.append(f"FAISS index directory not found: {faiss_index_dir}")
        else:
            faiss_file = os.path.join(faiss_index_dir, "face_index.faiss")
            if not os.path.isfile(faiss_file):
                errors.append(f"FAISS index file not found: {faiss_file}")
                
        if not videos_dir or not os.path.isdir(videos_dir):
            warnings.append(f"Videos directory not found: {videos_dir}")
            
    except Exception as e:
        errors.append(f"Validation exception: {str(e)}")

    status = "ok"
    if warnings:
        status = "warning"
    if errors:
        status = "error"
        
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "restartRequired": True
    }

@router.post("/config/validate")
def validate_config(payload: DesktopConfigPayload):
    if os.environ.get("DESKTOP_MODE", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Desktop mode is not enabled.")
        
    return _validate_config(payload.dict())

@router.post("/config/save")
def save_config(payload: DesktopConfigPayload):
    if os.environ.get("DESKTOP_MODE", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Desktop mode is not enabled.")
        
    config_path = os.environ.get("CONFIG_PATH")
    if not config_path:
        raise HTTPException(status_code=400, detail="CONFIG_PATH not set.")
        
    config_dict = payload.dict()
    val_result = _validate_config(config_dict)
    
    if val_result["errors"]:
        # Block save if there are critical errors
        return val_result
        
    # Atomic save
    try:
        # Create temp file
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(config_path), text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2)
            
        # Create backup if original exists
        if os.path.exists(config_path):
            bak_path = config_path + ".bak"
            shutil.copy2(config_path, bak_path)
            
        # Atomically replace
        os.replace(temp_path, config_path)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")
        
    return val_result
