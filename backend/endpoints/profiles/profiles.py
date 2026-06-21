from fastapi import APIRouter, UploadFile
from fastapi.responses import StreamingResponse

import asyncio
import hashlib

router = APIRouter()


@router.post("/profiles/stream")
async def process_profile_endpoint(file: UploadFile):
  

POST /profiles
  upload CSV
  returns profile_id immediately

GET /profiles/{profile_id}/events
  streams backend progress with SSE