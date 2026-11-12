from datetime import datetime
from toutiao_backend.schemas.news import NewsItemBase
from pydantic import BaseModel, Field, ConfigDict



class FavoriteCheckResponse(BaseModel):
    is_favorite: bool = Field(..., alias="isFavorite")


class FavoriteAddRequest(BaseModel):
    news_id: int = Field(..., alias="newsId")

#一个是新闻模型类，一个是收藏模型类
class FavoriteItemBase(NewsItemBase):
    favorite_id: int = Field(..., alias="favoriteId")
    favorite_time: datetime = Field(..., alias="favoriteTime")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

# 收藏列表接口响应模型类
class FavoriteListResponse(BaseModel):
    list: list[FavoriteItemBase]
    total: int
    has_more: bool=Field(...,alias="hasMore")
    model_config=ConfigDict(from_attributes=True,pulate_by_name=True)
