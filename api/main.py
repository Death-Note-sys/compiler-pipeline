from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="NL App Compiler Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

@app.get("/")
def health():
    return {"status": "ok", "message": "Pipeline API is live"}

@app.post("/generate")
def generate(req: PromptRequest):
    return {
        "status": "building",
        "prompt": req.prompt,
        "message": "Full pipeline coming soon"
    }
