from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from toutiao_backend.utils.exception import http_exception_handler, integrity_error_handler, sqlalchemy_error_handler,general_exception_handler

def register_exception_handlers(app):
    """
    注册全局异常处理器：子类在前，父类在后，具体的在前面，抽象的在后面
    """
    app.add_exception_handler(HTTPException, http_exception_handler) #这个是业务层的报错
    app.add_exception_handler(IntegrityError, integrity_error_handler) #数据完整性约束错误
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler) #这个是数据库层的报错
    app.add_exception_handler(Exception, general_exception_handler) #这个是通用的报错