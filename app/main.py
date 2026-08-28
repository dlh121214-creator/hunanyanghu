from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import Settings, load_settings
from app.dependencies import (
    build_judge_service,
    build_keyword_matcher,
    build_knowledge_provider,
    build_compose_service,
    build_network_search_provider,
)
from app.errors import AppError
from app.routes import router
from app.schemas import ErrorBody, ErrorResponse, HealthResponse
from app.store import InMemoryWorkflowStore


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or load_settings()
    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        description=(
            "工程类型识别、候选确认、知识检索、多工程整理和问题上报接口。"
            "所有业务接口统一位于 /api/v1。"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = active_settings
    app.state.judge_service = build_judge_service(active_settings)
    app.state.keyword_matcher = build_keyword_matcher(active_settings)
    app.state.workflow_store = InMemoryWorkflowStore()
    app.state.knowledge_provider = build_knowledge_provider(active_settings)
    app.state.compose_service = build_compose_service(active_settings)
    app.state.network_search_provider = build_network_search_provider(active_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(
            uuid.uuid4()
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                request_id=_request_id(request),
                details=exc.details,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(body))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        serializable_errors = []
        for raw_error in exc.errors():
            error = dict(raw_error)
            if "ctx" in error:
                error["ctx"] = {
                    key: str(value) for key, value in error["ctx"].items()
                }
            serializable_errors.append(error)
        body = ErrorResponse(
            error=ErrorBody(
                code="VALIDATION_ERROR",
                message="请求参数校验失败",
                request_id=_request_id(request),
                details={"errors": serializable_errors},
            )
        )
        return JSONResponse(status_code=422, content=jsonable_encoder(body))

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="服务健康检查",
        tags=["系统"],
    )
    async def health() -> HealthResponse:
        return HealthResponse(
            service=active_settings.app_name,
            version=active_settings.app_version,
            environment=active_settings.environment,
        )

    app.include_router(router)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # 使用相对资源路径，使测试页面既能由服务提供，也能直接打开本地HTML。
    @app.get("/styles.css", include_in_schema=False)
    async def test_page_styles() -> FileResponse:
        return FileResponse(static_dir / "styles.css", media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    async def test_page_script() -> FileResponse:
        return FileResponse(
            static_dir / "app.js", media_type="application/javascript"
        )

    @app.get("/", include_in_schema=False)
    async def test_page() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
