import os
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import create_document, get_documents, db
from schemas import Study

# Optional heavy libs imported lazily in functions

app = FastAPI(title="Radiology DICOM Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure media folders exist
MEDIA_ROOT = os.path.abspath("media")
IMAGES_DIR = os.path.join(MEDIA_ROOT, "images")
THUMBS_DIR = os.path.join(MEDIA_ROOT, "thumbnails")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)

# Serve static files for rendered images
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")


@app.get("/")
def read_root():
    return {"message": "Radiology backend running", "media": "/media"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, "name", "✅ Connected")
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


class StudyOut(Study):
    id: Optional[str] = None


def _rescale_to_uint8(arr, window_center: Optional[float], window_width: Optional[float]):
    import numpy as np

    a = arr.astype(np.float32)

    # Apply windowing if provided
    if window_center is not None and window_width is not None and window_width > 0:
        lo = window_center - window_width / 2
        hi = window_center + window_width / 2
        a = np.clip(a, lo, hi)
        a = (a - lo) / (hi - lo)
    else:
        # Fallback: scale between min/max
        mn, mx = float(a.min()), float(a.max())
        if mx == mn:
            a = a * 0
        else:
            a = (a - mn) / (mx - mn)

    a = (a * 255.0).clip(0, 255).astype(np.uint8)
    return a


def _dicom_to_png_and_meta(content: bytes):
    import pydicom
    from PIL import Image
    import numpy as np

    ds = pydicom.dcmread(BytesIO(content))

    # Extract meta safely
    def g(tag, default=None):
        try:
            return str(getattr(ds, tag)) if hasattr(ds, tag) else default
        except Exception:
            return default

    patient_id = g("PatientID")
    patient_name = g("PatientName")
    modality = g("Modality")
    study_date = g("StudyDate")
    series_description = g("SeriesDescription")
    instance_number = None
    try:
        instance_number = int(getattr(ds, "InstanceNumber")) if hasattr(ds, "InstanceNumber") else None
    except Exception:
        instance_number = None

    window_center = None
    window_width = None
    try:
        wc = getattr(ds, "WindowCenter", None)
        ww = getattr(ds, "WindowWidth", None)
        # pydicom may return MultiValue
        if wc is not None:
            window_center = float(wc[0] if hasattr(wc, "__len__") else wc)
        if ww is not None:
            window_width = float(ww[0] if hasattr(ww, "__len__") else ww)
    except Exception:
        pass

    arr = ds.pixel_array

    # Apply rescale slope/intercept if present for CT
    try:
        import numpy as np
        slope = float(getattr(ds, "RescaleSlope", 1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))
        arr = (arr.astype(np.float32) * slope) + intercept
    except Exception:
        pass

    img8 = _rescale_to_uint8(arr, window_center, window_width)

    photometric_interpretation = g("PhotometricInterpretation")
    if photometric_interpretation == "MONOCHROME1":
        # Invert
        img8 = 255 - img8

    rows = int(getattr(ds, "Rows", img8.shape[0]))
    cols = int(getattr(ds, "Columns", img8.shape[1]))
    bits_allocated = int(getattr(ds, "BitsAllocated", 16))

    image = Image.fromarray(img8)

    # Create thumbnail
    thumb = image.copy()
    thumb.thumbnail((256, 256))

    # Save to disk
    import uuid
    uid = uuid.uuid4().hex
    img_rel = f"images/{uid}.png"
    thumb_rel = f"thumbnails/{uid}.png"
    image.save(os.path.join(MEDIA_ROOT, img_rel), format="PNG")
    thumb.save(os.path.join(MEDIA_ROOT, thumb_rel), format="PNG")

    meta = {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "modality": modality,
        "study_date": study_date,
        "series_description": series_description,
        "instance_number": instance_number,
        "rows": rows,
        "cols": cols,
        "bits_allocated": bits_allocated,
        "photometric_interpretation": photometric_interpretation,
        "window_center": window_center,
        "window_width": window_width,
        "image_path": f"/media/{img_rel}",
        "thumbnail_path": f"/media/{thumb_rel}",
    }
    return meta


@app.post("/api/studies/upload", response_model=StudyOut)
async def upload_dicom(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".dcm", ".dicom", ".img")):
        # allow unknown extension but warn
        pass
    try:
        content = await file.read()
        meta = _dicom_to_png_and_meta(content)
        study = Study(**meta)
        doc_id = create_document("study", study)
        return StudyOut(**study.model_dump(), id=doc_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process DICOM: {str(e)}")


@app.get("/api/studies", response_model=List[StudyOut])
def list_studies(limit: int = 50):
    try:
        docs = get_documents("study", {}, limit)
        out: List[StudyOut] = []
        for d in docs:
            d_copy = {k: v for k, v in d.items() if k != "_id"}
            d_copy["id"] = str(d.get("_id"))
            out.append(StudyOut(**d_copy))
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
