import os
import json
import time
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from google.cloud import geminidataanalytics
from google.api_core import client_options
from google.protobuf.json_format import MessageToDict

app = FastAPI(title="CS Frotas - Nexus Data Agent")

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")
LOCATION = os.getenv("GCP_LOCATION", "us")
DATA_AGENT_ID = os.getenv("DATA_AGENT_ID", "your-data-agent-id")
APP_ACCESS_KEY = os.getenv("APP_ACCESS_KEY", "nexus-access-key")

# Rate Limit: 3 perguntas por minuto por IP
RATE_LIMIT_PER_MINUTE = 3
request_timestamps = defaultdict(list)

templates = Jinja2Templates(directory="web_app/templates")

class ChatRequest(BaseModel):
    message: str
    access_key: str

def parse_data_agent_stream(stream):
    intro_texts = []
    insights_texts = []
    sql_queries = []
    tables_md = []
    followups = []
    chart_configs = []

    table_already_received = False

    for resp in stream:
        resp_dict = MessageToDict(resp._pb)
        sm = resp_dict.get("systemMessage")
        if not sm:
            continue

        # 1. Textos e Perguntas Sugeridas
        text_obj = sm.get("text", {})
        parts = text_obj.get("parts", [])
        text_type = text_obj.get("textType", "")

        if "FOLLOWUP" in text_type:
            followups.extend(parts)
        elif "THOUGHT" not in text_type:
            for p in parts:
                if isinstance(p, str) and p.strip():
                    if table_already_received:
                        insights_texts.append(p.strip())
                    else:
                        intro_texts.append(p.strip())

        # 2. Gráfico Nativo (apenas quando o agente explicitamente retornar 'chart')
        if "chart" in sm and isinstance(sm["chart"], dict):
            chart_obj = sm["chart"]
            chart_res = chart_obj.get("result", {})
            if "vegaConfig" in chart_res:
                vega_spec = chart_res["vegaConfig"]
                if isinstance(vega_spec, str):
                    try:
                        vega_spec = json.loads(vega_spec)
                    except Exception:
                        pass
                chart_configs.append(vega_spec)

        # 3. SQL Gerada
        data_block = sm.get("data", {})
        if isinstance(data_block, dict):
            if "generatedSql" in data_block and isinstance(data_block["generatedSql"], str):
                sql_queries.append(data_block["generatedSql"])
            if "query" in data_block and isinstance(data_block.get("query"), str):
                sql_queries.append(data_block["query"])

        if "analysis" in sm and isinstance(sm["analysis"], dict):
            if "query" in sm["analysis"] and isinstance(sm["analysis"]["query"], str):
                sql_queries.append(sm["analysis"]["query"])

        # 4. Tabela de Dados (apenas se vier 'result' ou 'data')
        result_obj = data_block.get("result") if isinstance(data_block, dict) else None
        
        # Caso A: result.data
        if result_obj and isinstance(result_obj, dict):
            table_already_received = True
            schema_fields = result_obj.get("schema", {}).get("fields", [])
            cols = [f.get("name") for f in schema_fields if f.get("name")]
            rows = result_obj.get("data", [])
            
            if not cols and rows and isinstance(rows[0], dict):
                cols = list(rows[0].keys())

            if cols and rows:
                table_title = result_obj.get("name", "Resultado da Consulta")
                table_str = f"### 📊 {table_title.replace('_', ' ').title()}\n\n"
                table_str += "| " + " | ".join(cols) + " |\n"
                table_str += "| " + " | ".join(["---"] * len(cols)) + " |\n"
                for r in rows:
                    row_vals = [str(r.get(c, "-") if r.get(c) is not None else "-") for c in cols]
                    table_str += "| " + " | ".join(row_vals) + " |\n"
                tables_md.append(table_str)

        # Caso B: data.data
        elif "data" in data_block and isinstance(data_block["data"], list) and "schema" in data_block:
            table_already_received = True
            schema_fields = data_block.get("schema", {}).get("fields", [])
            cols = [f.get("name") for f in schema_fields if f.get("name")]
            rows = data_block["data"]
            if cols and rows:
                cleaned_rows = []
                for r in rows:
                    row_fields = r.get("fields", {}) if "fields" in r else r
                    cleaned_row = {}
                    for f in cols:
                        if isinstance(row_fields.get(f), dict):
                            f_info = row_fields.get(f, {})
                            val = (
                                f_info.get("stringValue")
                                or f_info.get("numberValue")
                                or f_info.get("boolValue")
                                or "-"
                            )
                        else:
                            val = row_fields.get(f, "-")
                        cleaned_row[f] = val
                    cleaned_rows.append(cleaned_row)
                
                table_str = "| " + " | ".join(cols) + " |\n"
                table_str += "| " + " | ".join(["---"] * len(cols)) + " |\n"
                for r in cleaned_rows:
                    row_vals = [str(r.get(f, "-")) for f in cols]
                    table_str += "| " + " | ".join(row_vals) + " |\n"
                tables_md.append(table_str)

    unique_sql = []
    for s in sql_queries:
        if s not in unique_sql:
            unique_sql.append(s)

    return {
        "intro": "\n\n".join(intro_texts).strip(),
        "tables": "\n\n".join(tables_md).strip(),
        "insights": "\n\n".join(insights_texts).strip(),
        "sql": "\n\n".join(unique_sql).strip(),
        "charts": chart_configs,
        "followups": followups
    }

def call_official_data_agent(user_prompt: str):
    opts = client_options.ClientOptions(api_endpoint=f"geminidataanalytics.{LOCATION}.rep.googleapis.com")
    chat_client = geminidataanalytics.DataChatServiceClient(client_options=opts)

    msg = geminidataanalytics.Message()
    msg.user_message.text = user_prompt

    data_agent_context = geminidataanalytics.DataAgentContext()
    data_agent_context.data_agent = f"projects/{PROJECT_ID}/locations/{LOCATION}/dataAgents/{DATA_AGENT_ID}"

    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        messages=[msg],
        data_agent_context=data_agent_context
    )

    stream = chat_client.chat(request=request, timeout=300)
    return parse_data_agent_stream(stream)

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/verify-key")
async def verify_key(req: dict):
    key = req.get("key", "")
    if key == APP_ACCESS_KEY:
        return {"valid": True}
    return JSONResponse(status_code=401, content={"valid": False, "error": "Chave de acesso inválida."})

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    # 1. Validação da Chave de Acesso
    if req.access_key != APP_ACCESS_KEY:
        return JSONResponse(
            status_code=401, 
            content={"intro": "🔒 Acesso não autorizado. Por favor, forneça a chave de acesso correta.", "tables": "", "insights": "", "sql": "", "charts": [], "followups": []}
        )

    # 2. Rate Limit (Máximo 3 perguntas por minuto por IP)
    client_ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    now = time.time()
    recent_requests = [t for t in request_timestamps[client_ip] if now - t < 60]
    
    if len(recent_requests) >= RATE_LIMIT_PER_MINUTE:
        seconds_to_wait = int(60 - (now - recent_requests[0]))
        return JSONResponse(
            status_code=429,
            content={
                "intro": f"⏳ **Limite de requisições atingido**: O limite é de {RATE_LIMIT_PER_MINUTE} perguntas por minuto por usuário para proteção de cota. Por favor, aguarde {seconds_to_wait} segundo(s) antes de enviar a próxima pergunta.",
                "tables": "",
                "insights": "",
                "sql": "",
                "charts": [],
                "followups": []
            }
        )

    recent_requests.append(now)
    request_timestamps[client_ip] = recent_requests

    # 3. Chamada da API
    try:
        result = call_official_data_agent(req.message)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            status_code=500, 
            content={"intro": f"❌ Erro na Conversational Analytics API: {str(e)}", "tables": "", "insights": "", "sql": "", "charts": [], "followups": []}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
