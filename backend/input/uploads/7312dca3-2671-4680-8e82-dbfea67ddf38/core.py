import os
import re
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List, Union

from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet

# ─── 1. DATABASE CONFIG & MODELS ──────────────────────────────────────────

DATABASE_URL = "sqlite:///./meetings.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String, unique=True, index=True)
    email = Column(String, index=True)
    google_refresh_token = Column(String, nullable=True)
    is_calendar_connected = Column(Boolean, default=False)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── 2. SCHEMAS (PYDANTIC) ───────────────────────────────────────────────

class MeetingRequest(BaseModel):
    date: str = Field(..., example="2025-05-20")
    time: str = Field(..., example="14:30")
    title: str = Field(..., description="The purpose or title of the meeting", example="Project Sync")

class MeetingResponse(BaseModel):
    success: bool
    event_id: str
    title: str
    start_ist: str
    end_ist: str
    calendar_link: str
    meet_link: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

class ErrorResponse(BaseModel):
    detail: str

# ─── 3. CALENDAR SERVICE LOGIC ───────────────────────────────────────────

TIMEZONE = "Asia/Kolkata"
IST = ZoneInfo(TIMEZONE)
MEETING_DURATION_MINUTES = 30
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

def _get_user_calendar_service(user: User):
    if not user.google_refresh_token:
        raise ValueError("User has not connected their Google Calendar.")

    refresh_token = user.google_refresh_token
    fernet_key = os.getenv("FERNET_KEY")
    if fernet_key:
        try:
            cipher = Fernet(fernet_key.encode())
            refresh_token = cipher.decrypt(user.google_refresh_token.encode()).decode()
        except Exception as e:
            print(f"DEBUG: Token decryption failed for {user.email}, using verbatim: {e}")
            refresh_token = user.google_refresh_token

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("calendar", "v3", credentials=creds)

def _parse_datetime_ist(date_str: str, time_str: str) -> datetime:
    time_str = time_str.strip()
    if re.search(r"[APap][Mm]", time_str):
        fmt = "%I:%M %p" if " " in time_str else "%I:%M%p"
        naive_time = datetime.strptime(time_str.upper(), fmt.upper())
    else:
        naive_time = datetime.strptime(time_str, "%H:%M")
    naive_date = datetime.strptime(date_str, "%Y-%m-%d")
    naive_dt = naive_date.replace(hour=naive_time.hour, minute=naive_time.minute, second=0, microsecond=0)
    return naive_dt.replace(tzinfo=IST)

async def create_calendar_event(user: User, payload: MeetingRequest) -> MeetingResponse:
    start_dt = _parse_datetime_ist(payload.date, payload.time)
    end_dt = start_dt + timedelta(minutes=MEETING_DURATION_MINUTES)
    now_ist = datetime.now(IST)
    if start_dt < now_ist:
        raise ValueError("Cannot schedule a meeting in the past.")

    service = _get_user_calendar_service(user)
    event_body = {
        "summary": payload.title,
        "description": f"Scheduled via Scedura Voice Agent.",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
        "conferenceData": {
            "createRequest": {
                "requestId": f"meet-{int(start_dt.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    created_event = service.events().insert(calendarId="primary", body=event_body, conferenceDataVersion=1).execute()
    
    meet_link = None
    conference = created_event.get("conferenceData")
    if conference:
        for ep in conference.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri")
                break

    return MeetingResponse(
        success=True,
        event_id=created_event["id"],
        title=created_event["summary"],
        start_ist=start_dt.isoformat(),
        end_ist=end_dt.isoformat(),
        calendar_link=created_event.get("htmlLink", ""),
        meet_link=meet_link,
    )

async def find_event(user: User, title: str, date: str) -> Optional[str]:
    service = _get_user_calendar_service(user)
    dt = datetime.strptime(date, "%Y-%m-%d")
    start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=IST)
    end_of_day = start_of_day + timedelta(days=1)
    
    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    
    for event in events_result.get("items", []):
        if title.lower() in event.get("summary", "").lower():
            return event["id"]
    return None

async def delete_event(user: User, event_id: str):
    service = _get_user_calendar_service(user)
    service.events().delete(calendarId="primary", eventId=event_id).execute()
