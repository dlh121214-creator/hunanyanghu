# 湖南养护工程施工交底参考系统—智能体服务

本项目实现工程描述分组、关键词候选匹配、员工确认、知识检索、多工程整理和问题上报接口。当前为工程识别和多工程整理分别配置独立的千问3-8B API；正式知识库尚未接入，知识内容暂时使用Mock数据。

## 启动

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动后访问：

- 测试页面：`http://127.0.0.1:8000/`
- Swagger：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`
- OpenAPI：`http://127.0.0.1:8000/openapi.json`

## 测试

```powershell
python -m pytest
```

## 当前运行配置

- 工程识别和多工程整理分别使用独立的 `qwen3-8b` API凭据，互不混用。
- 知识提供者默认为 `mock`，所有内容均标记为模拟数据。
- 网络搜索默认关闭；关闭时即使触发兜底规则也不会发起外部请求。
- 本地开发可由项目根目录 `.env` 注入配置；系统或容器环境变量优先级更高。
- `.env` 已被忽略，不得把API密钥写入源码、日志或接口文档。

## 配置两套8B API

复制 `.env.example` 为 `.env`，或将同名配置注入系统/容器环境变量：

```text
JUDGE_MODEL_PROVIDER=api
JUDGE_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
JUDGE_MODEL_API_KEY=***
JUDGE_MODEL_NAME=qwen3-8b

COMPOSE_MODEL_PROVIDER=api
COMPOSE_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
COMPOSE_MODEL_API_KEY=***
COMPOSE_MODEL_NAME=qwen3-8b
```

两个模型调用均按照OpenAI兼容的 `/chat/completions` 协议实现，并关闭思考模式。若生产接口地址或协议不同，只需调整配置或替换 `app/providers/model.py`，业务接口不变。

## 接入资料

- [智能体开发文档](./智能体开发文档.md)
- [团队接口文档](./docs/API接口文档.md)
- [OpenAPI规范](./docs/openapi.json)
