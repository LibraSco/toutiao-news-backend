from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
#响应的通用格式
def success_response( message: str="success", data: dict = None):
    #目标：把任何的格式（Fastapi，pydantic）都要正常响应
    response_data = {
        "code": 200,
        "message": message,
        "data": data
    }
    return JSONResponse(content=jsonable_encoder(response_data))

