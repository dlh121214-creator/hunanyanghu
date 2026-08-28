from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.schemas import (
    ConfirmedEngineeringType,
    ComposeRequest,
    ComposeResponse,
    CapabilitiesResponse,
    EngineeringCandidateGroup,
    IntentConfirmRequest,
    IntentConfirmResponse,
    IntentMatchRequest,
    IntentMatchResponse,
    IssueReportRequest,
    IssueReportResponse,
    KnowledgeItem,
    KnowledgeRetrieveRequest,
    KnowledgeRetrieveResponse,
    MissingKnowledgeItem,
)
from app.errors import AppError


router = APIRouter(prefix="/api/v1")


@router.get(
    "/system/capabilities",
    response_model=CapabilitiesResponse,
    summary="获取当前服务能力和开关",
    description="返回可公开的运行配置，不返回API密钥和内部地址。",
    tags=["系统"],
)
async def get_capabilities(request: Request) -> CapabilitiesResponse:
    settings = request.app.state.settings
    return CapabilitiesResponse(
        top_k=settings.top_k,
        match_threshold=settings.match_threshold,
        judge_model_provider=settings.judge_model_provider,
        compose_model_provider=settings.compose_model_provider,
        knowledge_provider=settings.knowledge_provider,
        network_search_enabled=settings.network_search_enabled,
        network_search_provider=settings.network_search_provider,
        multi_project_compose_enabled=settings.multi_project_compose_enabled,
        issue_report_enabled=settings.issue_report_enabled,
    )


@router.post(
    "/intent/match",
    response_model=IntentMatchResponse,
    summary="识别工程并返回标准标签候选",
    description=(
        "调用8B判断模型识别单个或多个工程，再通过关键词匹配为每个工程返回"
        "匹配度最高的标准工程标签。匹配度由关键词规则产生，不是模型置信度。"
    ),
    tags=["意图识别"],
)
async def match_intent(
    payload: IntentMatchRequest, request: Request
) -> IntentMatchResponse:
    judge_service = request.app.state.judge_service
    matcher = request.app.state.keyword_matcher
    extraction = await judge_service.analyze(payload.employee_input)
    groups: list[EngineeringCandidateGroup] = []
    for group in extraction.engineering_groups:
        candidates = matcher.match(group.engineering_description)
        groups.append(
            EngineeringCandidateGroup(
                group_id=group.group_id,
                engineering_description=group.engineering_description,
                candidates=candidates,
                network_fallback_required=not any(
                    item.above_threshold for item in candidates
                ),
            )
        )
    response = IntentMatchResponse(
        request_id=str(uuid.uuid4()),
        top_k=matcher.top_k,
        match_threshold=matcher.threshold,
        engineering_groups=groups,
    )
    await request.app.state.workflow_store.save_match(
        response.request_id,
        {
            "session_id": payload.session_id,
            "employee_input": payload.employee_input,
            "response": response.model_dump(),
        },
    )
    return response


@router.post(
    "/intent/confirm",
    response_model=IntentConfirmResponse,
    summary="确认工程类型候选",
    description=(
        "员工必须为每个工程分组选择一个候选标准标签，或明确选择网络搜索兜底。"
        "不能提交候选列表之外的标准标签。"
    ),
    tags=["意图识别"],
)
async def confirm_intent(
    payload: IntentConfirmRequest, request: Request
) -> IntentConfirmResponse:
    stored = await request.app.state.workflow_store.get_match(payload.request_id)
    if not stored:
        raise AppError(
            code="MATCH_REQUEST_NOT_FOUND",
            message="未找到对应的工程识别请求",
            status_code=404,
        )

    group_map = {
        group["group_id"]: group
        for group in stored["response"]["engineering_groups"]
    }
    selection_map = {selection.group_id: selection for selection in payload.selections}
    if len(selection_map) != len(payload.selections):
        raise AppError(
            code="DUPLICATE_GROUP_SELECTION",
            message="同一工程分组不能重复选择",
            status_code=422,
        )
    missing_groups = sorted(set(group_map) - set(selection_map))
    unknown_groups = sorted(set(selection_map) - set(group_map))
    if missing_groups or unknown_groups:
        raise AppError(
            code="INCOMPLETE_GROUP_SELECTION",
            message="必须为每个工程分组完成选择",
            status_code=422,
            details={
                "missing_group_ids": missing_groups,
                "unknown_group_ids": unknown_groups,
            },
        )

    confirmed: list[ConfirmedEngineeringType] = []
    has_local = False
    has_network = False
    for group_id, selection in selection_map.items():
        group = group_map[group_id]
        if selection.use_network_fallback:
            has_network = True
            confirmed.append(
                ConfirmedEngineeringType(
                    group_id=group_id,
                    use_network_fallback=True,
                    search_query=group["engineering_description"],
                )
            )
            continue

        candidate = next(
            (
                item
                for item in group["candidates"]
                if item["type_id"] == selection.type_id
            ),
            None,
        )
        if candidate is None:
            raise AppError(
                code="TYPE_NOT_IN_CANDIDATES",
                message="只能选择当前工程分组返回的候选标签",
                status_code=422,
                details={"group_id": group_id, "type_id": selection.type_id},
            )
        has_local = True
        confirmed.append(
            ConfirmedEngineeringType(
                group_id=group_id,
                type_id=candidate["type_id"],
                type_name=candidate["type_name"],
            )
        )

    if has_local and has_network:
        next_action = "mixed_retrieve"
    elif has_network:
        next_action = "network_fallback"
    else:
        next_action = "retrieve"
    response = IntentConfirmResponse(
        request_id=payload.request_id,
        confirmed_types=confirmed,
        next_action=next_action,
    )
    await request.app.state.workflow_store.save_confirmation(
        payload.request_id, response.model_dump()
    )
    return response


@router.post(
    "/issues/report",
    response_model=IssueReportResponse,
    summary="上报缺失工程类型",
    description="记录员工提交的缺失工程类型，供后续业务人员处理。",
    tags=["问题上报"],
)
async def report_issue(
    payload: IssueReportRequest, request: Request
) -> IssueReportResponse:
    if not request.app.state.settings.issue_report_enabled:
        raise AppError(
            code="ISSUE_REPORT_DISABLED",
            message="问题上报功能已禁用",
            status_code=503,
        )
    report_id = str(uuid.uuid4())
    original_input = payload.original_input
    candidate_snapshot = None
    if payload.request_id:
        stored = await request.app.state.workflow_store.get_match(payload.request_id)
        if stored:
            original_input = original_input or stored["employee_input"]
            candidate_snapshot = stored["response"]["engineering_groups"]
    await request.app.state.workflow_store.save_issue(
        report_id,
        {
            **payload.model_dump(),
            "original_input": original_input,
            "candidate_snapshot": candidate_snapshot,
        },
    )
    return IssueReportResponse(
        report_id=report_id,
        message=f"已上报：缺失“{payload.missing_type_name}”类型工程",
    )


@router.post(
    "/knowledge/retrieve",
    response_model=KnowledgeRetrieveResponse,
    summary="检索已确认工程的养护内容",
    description=(
        "根据当前请求中员工已确认的工程类型查询知识内容。当前开发阶段使用Mock提供者；"
        "单工程返回direct，多工程返回compose。无本地内容时标记为需要网络兜底。"
    ),
    tags=["知识检索"],
)
async def retrieve_knowledge(
    payload: KnowledgeRetrieveRequest, request: Request
) -> KnowledgeRetrieveResponse:
    confirmation = await request.app.state.workflow_store.get_confirmation(
        payload.request_id
    )
    if not confirmation:
        raise AppError(
            code="CONFIRMATION_NOT_FOUND",
            message="请先完成工程类型确认",
            status_code=409,
        )

    provider = request.app.state.knowledge_provider
    items: list[KnowledgeItem] = []
    missing: list[MissingKnowledgeItem] = []
    seen_type_ids: set[str] = set()
    for confirmed in confirmation["confirmed_types"]:
        if confirmed["use_network_fallback"]:
            missing.append(
                MissingKnowledgeItem(
                    group_id=confirmed["group_id"],
                    search_query=confirmed["search_query"],
                    reason="employee_requested_network_fallback",
                )
            )
            continue
        type_id = confirmed["type_id"]
        if type_id in seen_type_ids:
            continue
        seen_type_ids.add(type_id)
        item = await provider.retrieve(
            group_id=confirmed["group_id"],
            type_id=type_id,
            type_name=confirmed["type_name"],
        )
        if item is None:
            missing.append(
                MissingKnowledgeItem(
                    group_id=confirmed["group_id"],
                    type_id=type_id,
                    type_name=confirmed["type_name"],
                    search_query=confirmed["type_name"],
                    reason="local_knowledge_not_found",
                )
            )
        else:
            items.append(item)

    if missing and payload.allow_network_fallback:
        settings = request.app.state.settings
        if settings.network_search_fallback_enabled and settings.network_search_enabled:
            still_missing: list[MissingKnowledgeItem] = []
            for missing_item in missing:
                network_item = await request.app.state.network_search_provider.search(
                    group_id=missing_item.group_id,
                    query=missing_item.search_query,
                )
                if network_item is None:
                    still_missing.append(
                        missing_item.model_copy(update={"reason": "network_search_no_result"})
                    )
                else:
                    items.append(network_item)
            missing = still_missing
        else:
            missing = [
                item.model_copy(update={"reason": "network_search_disabled"})
                for item in missing
            ]

    if missing:
        status = "fallback_required"
    else:
        status = "ready"
    total_effective = len(items) + len(missing)
    if total_effective == 0:
        output_mode = "unavailable"
    elif total_effective == 1:
        output_mode = "direct"
    else:
        output_mode = "compose"
    response = KnowledgeRetrieveResponse(
        request_id=payload.request_id,
        status=status,
        output_mode=output_mode,
        contains_external_content=any(
            item.source_type == "network" for item in items
        ),
        items=items,
        missing_items=missing,
    )
    await request.app.state.workflow_store.save_retrieval(
        payload.request_id, response.model_dump()
    )
    return response


@router.post(
    "/output/compose",
    response_model=ComposeResponse,
    summary="整理多个工程的综合内容",
    description=(
        "读取当前请求最近一次知识检索结果。只有至少两项有效工程内容时调用8B模型；"
        "结果未通过工程类型、来源及受保护内容校验时，自动降级为分工程展示。"
    ),
    tags=["内容输出"],
)
async def compose_output(
    payload: ComposeRequest, request: Request
) -> ComposeResponse:
    if not request.app.state.settings.multi_project_compose_enabled:
        raise AppError(
            code="COMPOSE_DISABLED",
            message="多工程整理功能已禁用",
            status_code=503,
        )
    retrieval = await request.app.state.workflow_store.get_retrieval(
        payload.request_id
    )
    if not retrieval:
        raise AppError(
            code="RETRIEVAL_NOT_FOUND",
            message="请先完成养护内容检索",
            status_code=409,
        )
    items = [KnowledgeItem.model_validate(item) for item in retrieval["items"]]
    return await request.app.state.compose_service.compose(
        request_id=payload.request_id, items=items
    )
