from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

import asyncio
import json
import os
import secrets
import traceback
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import random 
import logging
from pymongo import MongoClient
import uvicorn
import nest_asyncio

from pydantic import BaseModel

if __package__:
    # Project-root execution: uvicorn backend.app:app
    from .main import run_research_agent
else:
    # Render/direct execution from the backend directory: uvicorn app:app
    from main import run_research_agent


load_dotenv()

nest_asyncio.apply()

logger = logging.getLogger(__name__)


app = FastAPI()


MONGO_URI = os.getenv("MONGO_URI", "").strip()

# MongoDB is not used by the current request flow. Keep it optional so a
# serverless deployment can start without an unused database connection.
client = MongoClient(MONGO_URI) if MONGO_URI else None
db = client["research"] if client is not None else None
history = db["History"] if db is not None else None


# --------------------------------------------------
# CORS
# --------------------------------------------------

frontend_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        # NOTE: put your original default value here.
       "http://localhost:3000,"
            "http://127.0.0.1:3000,"
            "https://research-drab-omega.vercel.app"

    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    # Supports Vercel production, preview, and branch deployment URLs.
    allow_origin_regex=(
        r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?"
        r"|https://.*\.vercel\.app)$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




# --------------------------------------------------
# Request Models
# --------------------------------------------------

class ResearchRequest(BaseModel):
    message: str
   


# --------------------------------------------------
# Research API
# --------------------------------------------------



from datetime import datetime, timezone, timedelta
from fastapi.responses import JSONResponse

@app.post("/api/research")
def research_agent(request_data: ResearchRequest):

   
    user_message = request_data.message.strip()

    if not user_message:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Message cannot be empty."
            }
        )

    # Check daily limit
  



    try:
        result = run_research_agent(
            user_input=user_message
        )

        return JSONResponse(
            content={
                "success": True,
                **result,
                "usage": None
            }
        )

    except Exception as e:

        # Keep the client response generic, but never hide the real server
        # error. Without this traceback a 500 from the research graph cannot
        # be diagnosed from the Uvicorn log.
        logger.exception("Research request failed")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": (
                    str(e)
                    if os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes"}
                    else "Research failed."
                )
            }
        )


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/")
def start():

    return {
        "message": "Research Agent backend is running."
    }


# --------------------------------------------------
# Run Server
# --------------------------------------------------

if __name__ == "__main__":

    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
