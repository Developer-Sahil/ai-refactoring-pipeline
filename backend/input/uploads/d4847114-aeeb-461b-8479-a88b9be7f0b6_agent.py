import json
import os
from datetime import datetime
from typing import Optional, List

from google import genai
from google.genai import types

from core import User, MeetingRequest, create_calendar_event, find_event, delete_event

class MeetingAgent:
    def __init__(self, user: User):
        self.user = user
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model_id = "gemini-2.0-flash"
        self.chat_history = [] 
        self.last_booked_link = None

    def _get_tools(self):
        return [types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="book_meeting",
                description="Book a 30-minute meeting on the calendar.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "date": types.Schema(type="STRING", description="YYYY-MM-DD"),
                        "time": types.Schema(type="STRING", description="HH:MM (24h) or H:MM AM/PM"),
                        "title": types.Schema(type="STRING", description="Purpose/Title of the meeting"),
                    },
                    required=["date", "time", "title"]
                )
            ),
            types.FunctionDeclaration(
                name="cancel_meeting",
                description="Cancel a meeting from the calendar.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "title": types.Schema(type="STRING", description="Purpose/Title of the meeting to cancel"),
                        "date": types.Schema(type="STRING", description="YYYY-MM-DD"),
                    },
                    required=["title", "date"]
                )
            )
        ])]

    async def chat(self, user_input: str, history: List = []) -> tuple[str, Optional[str]]:
        if history:
            self.chat_history = [types.Content(role=i["role"], parts=[types.Part(text=i["text"])]) 
                                for i in history if i.get("role") and i.get("text")]

        current_time = datetime.now().strftime("%A, %Y-%m-%d %H:%M")
        sys_instr = f"You are 'Scedura', a Voice Scheduling Agent. Current time: {current_time}. Help book/cancel meetings. Only ask for Date, Time, and Purpose (Title). We don't need the user's name or any other details."

        self.chat_history.append(types.Content(role="user", parts=[types.Part(text=user_input)]))

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id, contents=self.chat_history,
                config=types.GenerateContentConfig(system_instruction=sys_instr, tools=self._get_tools())
            )

            while response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
                self.chat_history.append(response.candidates[0].content)
                tool_results_parts = []
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        fc = part.function_call
                        result = await self._execute_tool(fc.name, fc.args)
                        tool_results_parts.append(types.Part(function_response=types.FunctionResponse(name=fc.name, response={"result": result})))
                
                if not tool_results_parts: break
                self.chat_history.append(types.Content(role="user", parts=tool_results_parts))
                response = await self.client.aio.models.generate_content(
                    model=self.model_id, contents=self.chat_history,
                    config=types.GenerateContentConfig(system_instruction=sys_instr, tools=self._get_tools())
                )

            self.chat_history.append(response.candidates[0].content)
            final_text = "".join([p.text for p in response.candidates[0].content.parts if p.text]) or "Processed."
            return final_text, self.last_booked_link

        except Exception as e:
            return f"Agent Error: {str(e)}", None

    async def _execute_tool(self, name: str, args: dict):
        try:
            if name == "book_meeting":
                req = MeetingRequest(date=args["date"], time=args["time"], title=args["title"])
                res = await create_calendar_event(self.user, req)
                self.last_booked_link = res.calendar_link
                return json.dumps(res.model_dump(), default=str)
            elif name == "cancel_meeting":
                event_id = await find_event(self.user, args["title"], args["date"])
                if not event_id: return "No meeting found with that purpose on that date."
                await delete_event(self.user, event_id)
                return "Successfully canceled."
        except Exception as e:
            return f"Error: {str(e)}"
        return "Unknown tool."
