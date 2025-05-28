from __future__ import annotations
import os, json, asyncio, requests
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai, cartesia, deepgram, silero

from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.plugins.noise_cancellation import BVC

# Load environment variables (e.g. NEXTJS_API_URL)
load_dotenv()

# ────────────── Prompt retrieval ──────────────
def parse_prompt_payload(ctx: agents.JobContext) -> dict[str, any]:
    """
    Extracts the interview prompt JSON from:
      1. Room metadata topic name (ctx.room._info.metadata => {"topic": "..."})
      2. Job input CLI --input or ctx.job_input (full JSON)

    If only a topic is provided, fetch the full catalogue from the web-app
    and select the matching entry. 

    The final JSON must contain:
      { "instructions": "...", "hard_skills": ["...", ...] }
    """
    # 1. Check metadata for JSON or topic
    room_info = getattr(ctx.room, "_info", None)
    if room_info is not None:
        meta_str = getattr(room_info, "metadata", None)
        if meta_str:
            try:
                meta = json.loads(meta_str)
            except json.JSONDecodeError:
                raise RuntimeError("Invalid room metadata JSON")
            # If full prompt provided
            if "instructions" in meta and "hard_skills" in meta:
                return meta
            # If only topic provided, fetch full catalogue
            if "topic" in meta:
                topic = meta["topic"]
                webapp = os.getenv("NEXTJS_API_URL", "http://localhost:3000").rstrip('/')
                url = f"{webapp}/api/prompts"
                try:
                    resp = requests.get(url, timeout=5)
                    resp.raise_for_status()
                    catalogue = resp.json()
                except Exception as e:
                    raise RuntimeError(f"Failed to fetch prompt catalogue: {e}")
                entry = next((p for p in catalogue if p.get("topic") == topic), None)
                if entry:
                    return entry
                else:
                    raise RuntimeError(f"Topic '{topic}' not found in catalogue")
    # 2. Job input (CLI or SDK)
    raw = getattr(ctx, "job_input", None) or getattr(ctx, "input", None)
    if raw:
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            raise RuntimeError("Invalid JSON provided as job input")

    raise RuntimeError(
        "No interview prompt supplied. Provide `{ topic: ..., instructions:, hard_skills: }` via room metadata or full JSON via job input."
    )

# ────────────── Agent builder ──────────────
def build_interviewer(instructions: str) -> type[Agent]:
    """Return an Agent subclass seeded with the given instructions."""
    class _Interviewer(Agent):
        def __init__(self) -> None:
            super().__init__(instructions=instructions.strip())

    return _Interviewer

# ────────────── Entry point ──────────────
async def entrypoint(ctx: agents.JobContext):
    # 1. Connect to LiveKit
    await ctx.connect()

    # 2. Load prompt (instructions + skills)
    prompt            = parse_prompt_payload(ctx)
    base_instructions = prompt["instructions"]
    hard_skills       = prompt.get("hard_skills", [])

    # 2a. Build the interviewer with embedded hard_skills
    full_instructions = (
        base_instructions.strip()
        + "\n\nPlease ask one question at a time covering each of the following skills:\n"
        + "\n".join(f"- {skill}" for skill in hard_skills)
    )
    interviewer = build_interviewer(full_instructions)

    # 3. Start voice session…
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=openai.LLM(model="gpt-4.1-nano"),
        tts=cartesia.TTS(),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    # 4. Collect transcripts
    transcript_segments: list[str] = []
    @session.on("conversation_item_added")
    def on_segment(event):
        if getattr(event, "is_final", False) and hasattr(event, "transcript"):
            text = event.transcript
            transcript_segments.append(text)
            asyncio.create_task(
                session.publish_event(
                    "transcription",
                    {"id": event.id, "text": text, "role": "user"}
                )
            )

    # 5. On shutdown, send analysis
    def push_analysis():
        full_txt = "\n".join(transcript_segments)
        try:
            requests.post(
                os.getenv("NEXTJS_API_URL", "http://localhost:3000") + "/api/analyze-transcript",
                json={"transcript": full_txt, "hardSkills": hard_skills},
                timeout=5,
            )
        except Exception as e:
            print("Failed to push analysis:", e)
    ctx.add_shutdown_callback(push_analysis)

    # 6. Run the interview
    await session.start(
        room=ctx.room,
        agent=interviewer(),
        room_input_options=RoomInputOptions(noise_cancellation=BVC(),),
    )

    # 7. First question
    await session.generate_reply(
        instructions="Welcome to your AI interview. Let’s begin: 'Can you tell me about yourself and your background?'"
    )

# ────────────── CLI runner ──────────────
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
