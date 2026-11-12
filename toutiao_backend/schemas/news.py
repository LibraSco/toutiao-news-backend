from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class NewsItemBase(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    image: Optional[str] = None
    author: Optional[str] = None
    category_id: int = Field(alias="categoryId")
    views: int
    publish_time: Optional[datetime] = Field(None, alias="publishedTime")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class NewsUpdateRequest(BaseModel):
    """部分更新：只传要改的字段，没传的保持原值"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    image: Optional[str] = Field(None, max_length=255)
    author: Optional[str] = Field(None, max_length=50)
    category_id: Optional[int] = Field(None, alias="categoryId")

    model_config = ConfigDict(populate_by_name=True)