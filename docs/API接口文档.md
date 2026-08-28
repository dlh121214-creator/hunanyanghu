# 智能体服务接口文档

## 1. 基本信息

- 当前版本：`v1`
- 基础路径：`/api/v1`
- 数据格式：`application/json; charset=utf-8`
- 在线Swagger：`/docs`
- 在线ReDoc：`/redoc`
- OpenAPI文件：`docs/openapi.json`
- 鉴权：当前独立测试阶段未启用；集成原业务系统时由双方确定统一鉴权方式。

所有响应均包含响应头：

```http
X-Request-ID: 业务系统传入的请求ID或服务端自动生成的UUID
```

业务系统可以主动传入 `X-Request-ID`，方便跨系统日志关联。

## 2. 标准错误格式

```json
{
  "error": {
    "code": "TYPE_NOT_IN_CANDIDATES",
    "message": "只能选择当前工程分组返回的候选标签",
    "request_id": "9b02b4bf-1d3f-4898-a9d0-7e9688cecf59",
    "details": {
      "group_id": "group_1",
      "type_id": "UNKNOWN"
    }
  }
}
```

调用方应使用 `error.code` 判断错误类型，不应依赖中文 `message`。

## 3. 推荐调用顺序

1. `POST /intent/match`：识别工程并获取每组Top 3候选。
2. 前端展示候选卡片，员工完成选择。
3. `POST /intent/confirm`：提交每个工程分组的选择。
4. `POST /knowledge/retrieve`：检索养护内容并执行允许的网络兜底。
5. `output_mode=direct`：直接展示 `items[0].content`，禁止调用整合模型。
6. `output_mode=compose`：调用 `POST /output/compose`。
7. `status=fallback_required`：展示缺失状态并允许调用问题上报。
8. `POST /issues/report`：员工确认提交缺失工程类型。

## 4. 接口列表

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| GET | `/api/v1/system/capabilities` | 查询当前功能开关 |
| POST | `/api/v1/intent/match` | 工程分组与Top 3标签匹配 |
| POST | `/api/v1/intent/confirm` | 员工确认工程标签或网络兜底 |
| POST | `/api/v1/knowledge/retrieve` | 检索本地或网络养护内容 |
| POST | `/api/v1/output/compose` | 使用独立的8B整合模型整理多个工程 |
| POST | `/api/v1/issues/report` | 上报缺失工程类型 |

## 5. 获取服务能力

```http
GET /api/v1/system/capabilities
```

响应示例：

```json
{
  "top_k": 3,
  "match_threshold": 70,
  "judge_model_provider": "api",
  "compose_model_provider": "api",
  "knowledge_provider": "mock",
  "network_search_enabled": false,
  "network_search_provider": "mock",
  "multi_project_compose_enabled": true,
  "issue_report_enabled": true
}
```

该接口不返回密钥和服务地址。

## 6. 工程识别与候选匹配

```http
POST /api/v1/intent/match
```

请求：

```json
{
  "session_id": "original-system-session-001",
  "employee_input": "对路面坑槽进行挖补，并重新铺筑沥青面层"
}
```

响应：

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75",
  "top_k": 3,
  "match_threshold": 70,
  "engineering_groups": [
    {
      "group_id": "group_1",
      "engineering_description": "对路面坑槽进行挖补",
      "candidates": [
        {
          "type_id": "ROAD_POTHOLE_REPAIR",
          "type_name": "坑槽修补",
          "match_score": 95,
          "above_threshold": true,
          "matched_keywords": ["坑槽", "挖补"]
        }
      ],
      "network_fallback_required": false
    }
  ]
}
```

说明：

- `match_score` 是关键词规则产生的匹配度，不是模型置信度。
- 每个工程分组最多返回3个候选。
- `network_fallback_required=true` 表示该分组没有候选达到阈值。

## 7. 员工确认

```http
POST /api/v1/intent/confirm
```

选择标准标签：

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75",
  "selections": [
    {
      "group_id": "group_1",
      "type_id": "ROAD_POTHOLE_REPAIR"
    }
  ]
}
```

选择网络搜索：

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75",
  "selections": [
    {
      "group_id": "group_1",
      "use_network_fallback": true
    }
  ]
}
```

约束：

- 每个工程分组必须且只能提交一项选择。
- `type_id` 与 `use_network_fallback=true` 不能同时提交。
- `type_id` 必须来自当前分组返回的候选列表。

## 8. 知识检索

```http
POST /api/v1/knowledge/retrieve
```

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75",
  "allow_network_fallback": true
}
```

重要字段：

- `status=ready`：已有可输出内容。
- `status=fallback_required`：仍有工程没有有效内容。
- `output_mode=direct`：只有一个工程，直接展示，禁止调用8B模型。
- `output_mode=compose`：存在多个工程，可调用整合接口。
- `source_type=local`：本地或正式知识来源。
- `source_type=network`：网络兜底来源，必须展示 `warning` 和来源链接。

## 9. 多工程整理

```http
POST /api/v1/output/compose
```

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75"
}
```

成功时：

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75",
  "status": "success",
  "output_mode": "composed",
  "content": "综合整理后的正文",
  "items": [],
  "contains_external_content": false,
  "warnings": [],
  "validation_errors": []
}
```

校验失败降级时：

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75",
  "status": "degraded",
  "output_mode": "separate",
  "content": null,
  "items": [],
  "contains_external_content": false,
  "warnings": ["整合结果未通过安全校验，已降级为分工程展示。"],
  "validation_errors": ["遗漏工程类型：坑槽修补"]
}
```

调用方遇到 `output_mode=separate` 时，应逐项展示 `items`，不能把降级当作无结果。

## 10. 问题上报

```http
POST /api/v1/issues/report
```

```json
{
  "request_id": "a7bb4f2a-7bd0-4f1a-8b59-7e651d525b75",
  "issue_type": "missing_engineering_type",
  "missing_type_name": "桥梁伸缩缝特殊处治",
  "employee_description": "前三个候选均不符合现场工程",
  "original_input": "现场原始工程描述"
}
```

`original_input`可以不传。服务会在能够找到 `request_id` 时自动补充原始输入和候选快照。

## 11. 主要错误码

| HTTP状态 | error.code | 含义 |
|---|---|---|
| 404 | `MATCH_REQUEST_NOT_FOUND` | 找不到识别请求 |
| 409 | `CONFIRMATION_NOT_FOUND` | 尚未完成员工确认 |
| 409 | `RETRIEVAL_NOT_FOUND` | 尚未完成知识检索 |
| 422 | `VALIDATION_ERROR` | 请求字段校验失败 |
| 422 | `INCOMPLETE_GROUP_SELECTION` | 工程分组未全部选择 |
| 422 | `TYPE_NOT_IN_CANDIDATES` | 提交了候选列表外的标签 |
| 422 | `COMPOSE_NOT_REQUIRED` | 单工程错误调用整合接口 |
| 502 | `MODEL_RESPONSE_INVALID` | 模型响应无法解析 |
| 502 | `MODEL_SCHEMA_VALIDATION_FAILED` | 8B识别模型输出未通过Schema校验 |
| 502 | `COMPOSE_VALIDATION_FAILED` | 8B结果未通过内容保护校验 |
| 502 | `NETWORK_SEARCH_UNAVAILABLE` | 网络搜索调用失败 |
| 503 | `MODEL_CONFIG_ERROR` | 模型配置缺失或不支持 |
| 503 | `COMPOSE_DISABLED` | 多工程整合被禁用 |
| 503 | `ISSUE_REPORT_DISABLED` | 问题上报被禁用 |
| 504 | `MODEL_TIMEOUT` | 模型API超时 |
| 504 | `NETWORK_SEARCH_TIMEOUT` | 网络搜索API超时 |

## 12. 集成注意事项

1. 原系统必须保存智能体返回的 `request_id`，后续确认、检索、整合均依赖该字段。
2. 原系统不要自行生成或修改 `type_id`。
3. 单工程直接展示知识内容，不调用整合接口。
4. 网络内容必须展示来源、链接和风险提示。
5. `degraded`是可展示的降级结果，不是接口失败。
6. 当前会话数据使用内存存储，生产集成前必须替换为数据库或Redis。
7. 当前未启用业务鉴权，生产集成前必须接入现有系统鉴权。
8. 正式知识库文件结构尚未确定，后续通过知识提供者适配层接入。
