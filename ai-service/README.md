# E-Review Agent AI Service

Independent FastAPI service for the E-Review Agent MVP.

## v1.5 LLM structured output

The service supports `qwen_openai_compatible`, `deepseek_openai_compatible`,
`local_qwen3_transformers`, `local_qwen3_openai_compatible`, and `local_rule_fallback`.
Provider secrets are read only from environment variables;
when the selected remote provider has no API key, review analysis automatically
uses the existing local rule workflow.

Endpoints:

- `POST /api/v1/llm/review/analyze`
- `GET /api/v1/llm/provider/status`
- `POST /api/v1/llm/schema/validate`
- `POST /api/v1/llm/schema/repair`
- `POST /api/v1/llm/local-qwen/smoke-test`

See `.env.example` for non-secret configuration names. Never commit a populated
`.env` file. The legacy `POST /api/v1/review/analyze` endpoint remains available
and now carries the same Provider and Schema metadata without changing its core
response fields.

The Transformers-based Qwen3 provider is optional and lazy-loaded. The normal
service still starts when `torch`, the model directory, or GPU memory is
unavailable; the response records the load error category and uses
`local_rule_fallback`. Model weights must remain outside this repository.

Current implementation uses mock sentiment analysis and a rule-based agent
workflow. It does not call any real deep learning model yet.

## Directory

```text
D:\EReviewAgent\ai-service
```

## Install

```powershell
cd D:\EReviewAgent\ai-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```powershell
cd D:\EReviewAgent\ai-service
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8008 --reload
```

## Health Check

```powershell
curl http://localhost:8008/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "E-Review Agent AI Service"
}
```

## Analyze Review

```powershell
curl -X POST http://localhost:8008/api/v1/review/analyze `
  -H "Content-Type: application/json" `
  -d "{\"review_id\":\"R001\",\"product_id\":\"P001\",\"product_name\":\"鐪熸棤绾块檷鍣€虫満\",\"review_text\":\"鑰虫満闊宠川涓嶉敊锛屼絾鏄画鑸竴鑸紝鍏呯數鐩掓湁鐐瑰鏄撶暀涓嬫寚绾广€俓",\"image_urls\":[\"http://example.com/a.jpg\"],\"rating\":4}"
```

## Test

```powershell
cd D:\EReviewAgent\ai-service
.venv\Scripts\activate
pytest
```

## Future Extension Points

- `app/models`: real multimodal sentiment model adapters
- `app/rag`: Qdrant or other vector retrieval modules
- `app/agents`: LangGraph workflow implementation
- `AnalyzerBase`: stable interface for mock and real analyzers
- `AgentWorkflowBase`: stable interface for rule and graph workflows
