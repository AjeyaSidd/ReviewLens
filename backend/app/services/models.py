from datetime import date, datetime
from pydantic import BaseModel, Field, model_validator
from typing import Optional
import uuid

class NormalizedReview(BaseModel):
    platform_review_id: str
    platform: str  # 'play_store' or 'app_store'
    rating: int = Field(ge=1, le=5)
    title: str = ""
    body: str = ""
    review_date: Optional[date] = None
    language: Optional[str] = None
    app_version: Optional[str] = None

    @property
    def has_text(self) -> bool:
        text = f"{self.title} {self.body}".strip()
        return len(text) > 0

    @property
    def full_text(self) -> str:
        return f"{self.title}. {self.body}".strip().strip(" .")



class SentimentResult(BaseModel):
    review_id: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    sentiment_label: str  # 'positive', 'neutral', 'negative'


class CatalogAppCreate(BaseModel):
    display_name: str
    country: str = "in"
    play_package: Optional[str] = None
    ios_app_id: Optional[str] = None
    app_icon_url: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_store(self):
        if not self.play_package and not self.ios_app_id:
            raise ValueError("At least one of play_package or ios_app_id must be provided")
        return self


class CatalogAppResponse(BaseModel):
    id: str
    display_name: str
    country: str
    play_package: Optional[str] = None
    ios_app_id: Optional[str] = None
    app_icon_url: Optional[str] = None
    is_active: bool
    scrape_status: str
    last_synced_at: Optional[datetime] = None
    review_count: int
    created_at: datetime
