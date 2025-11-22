"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# Example schemas (kept for reference):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Radiology DICOM study schema
class Study(BaseModel):
    """
    Radiology study metadata
    Collection name: "study"
    """
    patient_id: Optional[str] = Field(None, description="Patient ID from DICOM (0010,0020)")
    patient_name: Optional[str] = Field(None, description="Patient Name from DICOM (0010,0010)")
    modality: Optional[str] = Field(None, description="Modality, e.g., CT/MR/CR")
    study_date: Optional[str] = Field(None, description="Study date (YYYYMMDD)")
    series_description: Optional[str] = Field(None, description="Series description if present")
    instance_number: Optional[int] = Field(None, description="Instance number")
    rows: Optional[int] = Field(None, description="Rows in image")
    cols: Optional[int] = Field(None, description="Columns in image")
    bits_allocated: Optional[int] = Field(None, description="Bits allocated")
    photometric_interpretation: Optional[str] = Field(None, description="Photometric interpretation")
    window_center: Optional[float] = Field(None, description="Default window center")
    window_width: Optional[float] = Field(None, description="Default window width")
    image_path: Optional[str] = Field(None, description="Backend path to rendered PNG for this instance")
    thumbnail_path: Optional[str] = Field(None, description="Backend path to thumbnail PNG")
    findings: Optional[str] = Field(None, description="Optional AI/heuristic findings summary")
    tags: Optional[List[str]] = Field(default_factory=list, description="Optional tags")
