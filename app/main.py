"""FastAPI app: the call on the left, the co-pilot panel on the right.

HTMX drives the page. Every control posts to the server and gets the whole
stage back; while the call is playing, the stage carries a poller that
advances one beat per tick.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import engine, state as st

ROOT = Path(__file__).resolve().parent
TICK_SECONDS = 6

app = FastAPI(title="Spotter: agent assist for commercial lines service calls (demo)")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


def money(v) -> str:
    return f"${v:,.0f}"


templates.env.filters["money"] = money


def stage(request: Request, s: dict, flash: dict | None = None) -> HTMLResponse:
    n = s["beat"]
    ctx = {"s": s, "beats": engine.beats()[:n], "total": len(engine.beats()),
           "upcoming": engine.beats()[n] if n < len(engine.beats()) else None,
           "cards": engine.panel(s), "events": st.events(s["id"])[::-1],
           "call": engine.call()["call"], "tick": TICK_SECONDS, "flash": flash,
           "css_version": int((ROOT / "static" / "app.css").stat().st_mtime)}
    name = "index.html" if request.headers.get("HX-Request") != "true" else "stage.html"
    return templates.TemplateResponse(request, name, ctx)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return stage(request, st.load())


@app.get("/stage", response_class=HTMLResponse)
def get_stage(request: Request):
    return stage(request, st.load())


@app.post("/next", response_class=HTMLResponse)
def next_beat(request: Request):
    s = engine.advance(st.load())
    st.save(s)
    return stage(request, s)


@app.post("/tick", response_class=HTMLResponse)
def tick(request: Request):
    s = st.load()
    if s["playing"]:
        s = engine.advance(s)
        st.save(s)
    return stage(request, s)


@app.post("/play", response_class=HTMLResponse)
def play(request: Request):
    s = st.load()
    s["playing"] = s["beat"] < len(engine.beats())
    st.save(s)
    return stage(request, s)


@app.post("/pause", response_class=HTMLResponse)
def pause(request: Request):
    s = st.load()
    s["playing"] = False
    st.save(s)
    return stage(request, s)


@app.post("/restart", response_class=HTMLResponse)
def restart(request: Request):
    return stage(request, st.reset())


@app.post("/jump/{n}", response_class=HTMLResponse)
def jump(request: Request, n: int):
    """Presenter control: replay the call from the top to beat n, paused, no human actions taken."""
    s = st.reset()
    while s["beat"] < min(n, len(engine.beats())):
        s = engine.advance(s)
    st.save(s)
    return stage(request, s)


@app.post("/mark/{what}", response_class=HTMLResponse)
def mark(request: Request, what: str):
    s = engine.mark(st.load(), what)
    st.save(s)
    return stage(request, s)


@app.post("/certificate/issue", response_class=HTMLResponse)
def issue_certificate(request: Request):
    s, result = engine.issue_certificate(st.load())
    st.save(s)
    flash = None if result["issued"] else {"tone": "amber", "title": "Certificate refused", "text": result["reason"]}
    return stage(request, s, flash)


@app.post("/endorsement/start", response_class=HTMLResponse)
def start_endorsement(request: Request):
    s = engine.start_endorsement(st.load())
    st.save(s)
    return stage(request, s)


@app.post("/product/{status}", response_class=HTMLResponse)
def decide_product(request: Request, status: str):
    s = engine.decide_product(st.load(), status)
    st.save(s)
    return stage(request, s)


@app.post("/quote/request", response_class=HTMLResponse)
def request_quote(request: Request):
    s, result = engine.request_quote(st.load())
    st.save(s)
    flash = None if result["requested"] else {"tone": "amber", "title": "Quote request blocked", "text": result["reason"]}
    return stage(request, s, flash)


@app.post("/wrap/{kind}/accept", response_class=HTMLResponse)
def accept_draft(request: Request, kind: str, title: str = Form(...), body: str = Form(...)):
    s = engine.accept_draft(st.load(), kind, title, body)
    st.save(s)
    return stage(request, s)
