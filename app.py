"""
Iffy Business - a team icebreaker for laughs.

1. WRITE   Everyone draws a raffle number (1-999) and writes an "If..." question.
2. ANSWER  The questions are hidden. Everyone gets someone else's ticket and answers it blind.
3. REVEAL  The host opens the tickets one by one: question + answer. Everyone reacts.
4. WINNERS The funniest tickets win.

Shared game state lives in server memory (st.cache_resource), so everyone who opens
the same link plays the same game. A restart of the app resets the game.
"""

import html
import random
import threading
import time

import streamlit as st

st.set_page_config(page_title="Iffy Business", page_icon="🎟️", layout="centered")

MAX_LEN = 140
IDEAS = [
    "If our manager became a pirate?",
    "If Monday had a mascot?",
    "If the office kettle could talk?",
    "If Mark was the president of Seychelles?",
    "If every ticket reply had to rhyme?",
    "If we swapped jobs with the cleaners for a day?",
    "If the server room turned into a zoo?",
    "If lunch was served by drone?",
]
PHASES = [("write", "Write"), ("answer", "Answer"), ("reveal", "Reveal"), ("final", "Winners")]


# --------------------------------------------------------------------------- #
# Shared game state
# --------------------------------------------------------------------------- #
class Game:
    def __init__(self):
        self.lock = threading.RLock()
        self.reset()

    def reset(self):
        with self.lock:
            self.phase = "write"
            self.players = {}   # key -> display name
            self.entries = {}   # author key -> entry dict
            self.order = []     # reveal order (author keys)
            self.reveal_n = 0
            self.deadline = None

    # -- players ---------------------------------------------------------- #
    @staticmethod
    def key_of(name):
        return " ".join(name.lower().split())

    def join(self, name):
        key = self.key_of(name)
        with self.lock:
            self.players[key] = " ".join(name.split())
        return key

    # -- write phase ------------------------------------------------------ #
    def draw_number(self, key):
        with self.lock:
            if self.phase != "write":
                return
            used = {e["number"] for k, e in self.entries.items() if k != key}
            free = [n for n in range(1, 1000) if n not in used]
            number = random.choice(free)
            entry = self.entries.get(key)
            if entry is None:
                self.entries[key] = {
                    "name": self.players.get(key, key),
                    "number": number,
                    "question": "",
                    "answerer": None,
                    "answer": "",
                    "laughs": set(),
                    "hidden": False,
                }
            elif not entry["question"]:
                entry["number"] = number

    def save_question(self, key, text):
        with self.lock:
            entry = self.entries.get(key)
            if self.phase == "write" and entry and text.strip():
                entry["question"] = text.strip()[:MAX_LEN]

    # -- phase changes ---------------------------------------------------- #
    def start_answer(self):
        """Deal tickets: every writer answers exactly one ticket that is not theirs."""
        with self.lock:
            self.entries = {k: e for k, e in self.entries.items() if e["question"]}
            keys = list(self.entries)
            if len(keys) < 2:
                return False
            random.shuffle(keys)
            for i, k in enumerate(keys):
                self.entries[k]["answerer"] = keys[(i + 1) % len(keys)]
            self.phase = "answer"
            self.deadline = None
            return True

    def start_reveal(self):
        with self.lock:
            self.order = list(self.entries)
            random.shuffle(self.order)
            self.reveal_n = 0
            self.phase = "reveal"
            self.deadline = None

    def reveal_next(self):
        with self.lock:
            if self.reveal_n < len(self.order):
                self.reveal_n += 1
            else:
                self.phase = "final"

    def back(self):
        """Host rescue: step one phase backwards."""
        with self.lock:
            if self.phase == "final":
                self.phase = "reveal"
            elif self.phase == "reveal":
                self.reveal_n = 0
                self.phase = "answer"
            elif self.phase == "answer":
                for e in self.entries.values():
                    e["answerer"] = None
                    e["answer"] = ""
                self.phase = "write"
            self.deadline = None

    def start_timer(self, minutes):
        with self.lock:
            self.deadline = time.time() + minutes * 60

    # -- answer phase ----------------------------------------------------- #
    def ticket_for(self, key):
        with self.lock:
            for author, e in self.entries.items():
                if e["answerer"] == key:
                    return author, e
        return None, None

    def save_answer(self, key, text):
        with self.lock:
            _, e = self.ticket_for(key)
            if self.phase == "answer" and e and text.strip():
                e["answer"] = text.strip()[:MAX_LEN]

    # -- reveal phase ----------------------------------------------------- #
    def toggle_laugh(self, author, voter):
        with self.lock:
            e = self.entries.get(author)
            if e is None:
                return
            if voter in e["laughs"]:
                e["laughs"].discard(voter)
            else:
                e["laughs"].add(voter)

    def hide(self, author):
        with self.lock:
            if author in self.entries:
                self.entries[author]["hidden"] = True

    def snapshot(self):
        with self.lock:
            return (self.phase, self.reveal_n)


@st.cache_resource
def get_game(version=2):
    return Game()


game = get_game(2)


def host_pin():
    try:
        return str(st.secrets.get("HOST_PIN", "1234"))
    except Exception:
        return "1234"


# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bungee&family=DM+Sans:wght@400;500;700&display=swap');

html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp h3 {
  font-family: 'DM Sans', system-ui, sans-serif; }
[data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important; }
.block-container { max-width: 720px; padding-top: 4.5rem; padding-bottom: 4rem; }
#MainMenu, footer { visibility: hidden; }

.title { font-family: 'Bungee', 'Arial Black', Impact, sans-serif; font-size: clamp(2rem, 8vw, 3rem);
         line-height: 1; margin: 0; color: #fdf3dc; letter-spacing: .01em; }
.tagline { color: #bdb6e6; margin: .35rem 0 1.1rem 0; }

.steps { display: flex; gap: 6px; margin: 0 0 1.2rem 0; flex-wrap: wrap; }
.step { flex: 1 1 0; min-width: 70px; text-align: center; padding: .45rem .3rem;
        border-radius: 8px; background: #2a2660; color: #a49cd8; font-weight: 500; font-size: .9rem; }
.step.on { background: #fdf3dc; color: #1b1840; font-weight: 700; }
.step.past { background: #3a3585; color: #fdf3dc; }

.timer { font-family: 'Bungee', 'Arial Black', Impact, sans-serif; font-size: 1.5rem; color: #ffd166;
         text-align: center; margin: .3rem 0 1rem 0; }

/* ticket stubs */
.ticket { position: relative; display: flex; background: #fdf3dc; color: #1b1840;
          border-radius: 10px; margin: 0 0 1rem 0; overflow: hidden; }
.ticket .stub { flex: 0 0 96px; display: flex; align-items: center; justify-content: center;
                background: #e8452a; color: #fff; font-family: 'Bungee', 'Arial Black', Impact, sans-serif;
                font-size: 1.6rem; padding: 1rem .4rem; border-right: 3px dashed #1b1840; }
.ticket .body { flex: 1 1 auto; padding: .9rem 1.1rem; min-width: 0; }
.ticket .q { font-weight: 700; font-size: 1.1rem; line-height: 1.3; overflow-wrap: anywhere; }
.ticket .a { margin-top: .55rem; font-size: 1.05rem; line-height: 1.35; overflow-wrap: anywhere; }
.ticket .a b { color: #e8452a; }
.ticket .who { margin-top: .6rem; font-size: .8rem; color: #5b5780; }
.ticket.mini .stub { flex-basis: 74px; font-size: 1.2rem; padding: .6rem .3rem; }
.ticket.mini .body { padding: .6rem .9rem; }

/* ticket grid (answer phase, questions hidden) */
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 10px; margin: .6rem 0 1.2rem 0; }
.tile { background: #2a2660; border: 2px dashed #5b55b0; border-radius: 10px; color: #bdb6e6;
        text-align: center; padding: .6rem .2rem; }
.tile .n { display: block; font-family: 'Bungee', 'Arial Black', Impact, sans-serif; font-size: 1.15rem; }
.tile .s { display: block; font-size: .78rem; margin-top: .1rem; }
.tile.mine { background: #fdf3dc; color: #1b1840; border: 2px solid #ffd166; }
.tile.done { background: #1e5b57; border-color: #2ec4b6; color: #e6fffb; }

.bignum { font-family: 'Bungee', 'Arial Black', Impact, sans-serif; font-size: clamp(3rem, 16vw, 5.5rem); color: #fdf3dc;
          text-align: center; line-height: 1; margin: .4rem 0; }
.hint { color: #bdb6e6; font-size: .92rem; }
.podium { font-family: 'Bungee', 'Arial Black', Impact, sans-serif; font-size: 1.4rem; margin: 1.2rem 0 .5rem 0; color: #ffd166; }
.waiting { text-align: center; color: #bdb6e6; padding: 2rem 0; }

@media (max-width: 480px) {
  .ticket .stub { flex-basis: 76px; font-size: 1.25rem; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def esc(text):
    return html.escape(text or "")


def ticket_html(entry, show_answer=True, show_names=True, mini=False):
    answer = esc(entry["answer"]) if entry["answer"] else "<i>…silence. The answer got lost.</i>"
    ans_html = f'<div class="a"><b>Answer:</b> {answer}</div>' if show_answer else ""
    who = ""
    if show_names:
        answerer = game.players.get(entry["answerer"], "someone")
        who = f'<div class="who">Asked by {esc(entry["name"])}, answered by {esc(answerer)}</div>'
    cls = "ticket mini" if mini else "ticket"
    return (
        f'<div class="{cls}"><div class="stub">#{entry["number"]}</div>'
        f'<div class="body"><div class="q">{esc(entry["question"])}</div>{ans_html}{who}</div></div>'
    )


# --------------------------------------------------------------------------- #
# Reusable pieces
# --------------------------------------------------------------------------- #
def header():
    st.markdown('<p class="title">Iffy Business</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="tagline">Write an “If…” question. Answer someone else’s blind. Laugh at the result.</p>',
        unsafe_allow_html=True,
    )
    idx = [p for p, _ in PHASES].index(game.phase)
    pills = []
    for i, (_, label) in enumerate(PHASES):
        cls = "on" if i == idx else ("past" if i < idx else "")
        pills.append(f'<div class="step {cls}">{label}</div>')
    st.markdown(f'<div class="steps">{"".join(pills)}</div>', unsafe_allow_html=True)


@st.fragment(run_every=2)
def watcher():
    """Re-runs the whole page when the host changes the phase or reveals a ticket."""
    if game.snapshot() != st.session_state.get("snap"):
        st.rerun()


@st.fragment(run_every=1)
def countdown():
    d = game.deadline
    if not d or game.phase not in ("write", "answer"):
        return
    left = int(d - time.time())
    if left > 0:
        m, s = divmod(left, 60)
        st.markdown(f'<div class="timer">⏳ {m:02d}:{s:02d}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="timer">⌛ Time is up. Waiting for the host.</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Phase views
# --------------------------------------------------------------------------- #
@st.fragment(run_every=3)
def write_progress():
    with game.lock:
        saved = sum(1 for e in game.entries.values() if e["question"])
        total = max(len(game.players), saved)
    st.caption(f"{saved} of {total} players have saved a question")


def view_write(key):
    countdown()
    entry = game.entries.get(key)

    if entry is None:
        st.markdown("### Get your ticket")
        st.write("Press the button to draw your random number from 1 to 999.")
        if st.button("🎟️ Draw my number", type="primary", use_container_width=True):
            game.draw_number(key)
            st.rerun()
        write_progress()
        return

    st.markdown(f'<div class="bignum">#{entry["number"]}</div>', unsafe_allow_html=True)
    if not entry["question"]:
        if st.button("🔄 Draw a different number", use_container_width=True):
            game.draw_number(key)
            st.rerun()

    st.markdown("### Write your “If…” question")
    with st.form("question_form", clear_on_submit=False):
        text = st.text_area(
            "Your question",
            value=entry["question"],
            max_chars=MAX_LEN,
            height=100,
            placeholder="If Mark was the president of Seychelles?",
            label_visibility="collapsed",
        )
        saved = st.form_submit_button(
            "Save question" if not entry["question"] else "Update question",
            type="primary",
            use_container_width=True,
        )
    if saved:
        if text.strip():
            game.save_question(key, text)
            st.rerun()
        else:
            st.warning("Write your question before saving.")

    if entry["question"]:
        st.success("Saved. You can still edit it until the host closes this round.")
    with st.expander("Stuck? Get an idea"):
        st.write(random.choice(IDEAS))
        st.caption("Keep it silly, not about a real colleague's weak spots.")
    write_progress()


@st.fragment(run_every=3)
def answer_board(key):
    with game.lock:
        entries = sorted(game.entries.values(), key=lambda e: e["number"])
        done = sum(1 for e in entries if e["answer"])
    cells = []
    for e in entries:
        if e["answerer"] == key:
            cls, sub = "tile mine", "yours"
        elif e["answer"]:
            cls, sub = "tile done", "answered"
        else:
            cls, sub = "tile", "waiting"
        cells.append(f'<div class="{cls}"><span class="n">#{e["number"]}</span><span class="s">{sub}</span></div>')
    st.markdown(f'<div class="grid">{"".join(cells)}</div>', unsafe_allow_html=True)
    st.caption(f"{done} of {len(entries)} tickets answered")


def view_answer(key):
    countdown()
    author, entry = game.ticket_for(key)
    if entry is None:
        st.markdown('<div class="waiting">You did not write a question this round, so you are watching.<br>'
                    'Stay here for the reveal.</div>', unsafe_allow_html=True)
        answer_board(key)
        return

    st.markdown("### Your ticket")
    st.markdown(f'<div class="bignum">#{entry["number"]}</div>', unsafe_allow_html=True)
    st.write("The question is hidden. Write any answer you like, the sillier the better.")
    with st.form("answer_form"):
        text = st.text_area(
            "Your answer",
            value=entry["answer"],
            max_chars=MAX_LEN,
            height=100,
            placeholder="Only on Tuesdays, with extra chips.",
            label_visibility="collapsed",
        )
        saved = st.form_submit_button(
            "Save answer" if not entry["answer"] else "Update answer",
            type="primary",
            use_container_width=True,
        )
    if saved:
        if text.strip():
            game.save_answer(key, text)
            st.rerun()
        else:
            st.warning("Write your answer before saving.")
    if entry["answer"]:
        st.success("Saved. You can still edit it until the host starts the reveal.")
    st.markdown("### All tickets")
    answer_board(key)


@st.fragment(run_every=2)
def reveal_board(key, is_host):
    with game.lock:
        shown = [k for k in game.order[: game.reveal_n] if not game.entries[k]["hidden"]]
        total = len(game.order)
        n = game.reveal_n
    if n == 0:
        st.markdown('<div class="waiting">🥁 Waiting for the host to open the first ticket…</div>',
                    unsafe_allow_html=True)
        return
    for k in reversed(shown):
        e = game.entries[k]
        st.markdown(ticket_html(e), unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        mine = key in e["laughs"]
        c1.button(
            f"😂 {len(e['laughs'])}" + ("  (you laughed)" if mine else ""),
            key=f"laugh_{k}",
            on_click=game.toggle_laugh,
            args=(k, key),
            type="primary" if mine else "secondary",
            use_container_width=True,
        )
        if is_host:
            c2.button("Skip", key=f"hide_{k}", on_click=game.hide, args=(k,), use_container_width=True)
    st.caption(f"{n} of {total} tickets opened")


def view_reveal(key, is_host):
    if is_host:
        total, n = len(game.order), game.reveal_n
        label = f"👀 Open next ticket ({n}/{total})" if n < total else "🏆 Show the winners"
        if st.button(label, type="primary", use_container_width=True):
            game.reveal_next()
            st.rerun()
    reveal_board(key, is_host)


def view_final():
    if not st.session_state.get("balloons_done"):
        st.balloons()
        st.session_state.balloons_done = True
    with game.lock:
        entries = [e for e in game.entries.values() if not e["hidden"]]
    ranked = sorted(entries, key=lambda e: (-len(e["laughs"]), e["number"]))
    if not ranked:
        st.info("No tickets to show.")
        return
    medals = ["🥇", "🥈", "🥉"]
    st.markdown('<div class="podium">The funniest tickets</div>', unsafe_allow_html=True)
    for i, e in enumerate(ranked[:3]):
        st.markdown(f"**{medals[i]} {len(e['laughs'])} laughs**")
        st.markdown(ticket_html(e), unsafe_allow_html=True)
    rest = ranked[3:]
    if rest:
        st.markdown('<div class="podium">The rest</div>', unsafe_allow_html=True)
        for e in rest:
            st.markdown(f"**{len(e['laughs'])} 😂**")
            st.markdown(ticket_html(e, mini=True), unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Host controls
# --------------------------------------------------------------------------- #
def host_panel():
    with st.expander("🎛️ Host controls", expanded=bool(st.session_state.get("is_host"))):
        if not st.session_state.get("is_host"):
            with st.form("pin_form"):
                pin = st.text_input("Host PIN", type="password")
                if st.form_submit_button("Unlock"):
                    if pin == host_pin():
                        st.session_state.is_host = True
                        st.rerun()
                    else:
                        st.error("Wrong PIN.")
            return

        phase = game.phase
        label = dict(PHASES)[phase]
        st.caption(f"You are the host. Current round: **{label}**")

        if phase in ("write", "answer"):
            c1, c2 = st.columns([1, 1])
            minutes = c1.number_input("Minutes", min_value=1, max_value=15, value=3, step=1)
            c2.write("")
            c2.write("")
            if c2.button("Start countdown", use_container_width=True):
                game.start_timer(minutes)
                st.rerun()

        if phase == "write":
            saved = [e for e in game.entries.values() if e["question"]]
            waiting = [n for k, n in game.players.items()
                       if k not in game.entries or not game.entries[k]["question"]]
            st.write(f"**{len(saved)}** questions saved.")
            if waiting:
                st.caption("Still writing: " + ", ".join(waiting))
            if st.button("Close writing and deal tickets", type="primary", use_container_width=True):
                if game.start_answer():
                    st.rerun()
                else:
                    st.warning("At least 2 saved questions are needed to start.")

        elif phase == "answer":
            waiting = [game.players.get(e["answerer"], "?") for e in game.entries.values() if not e["answer"]]
            st.write(f"**{len(game.entries) - len(waiting)}** of {len(game.entries)} answered.")
            if waiting:
                st.caption("Still answering: " + ", ".join(waiting))
            if st.button("Start the reveal", type="primary", use_container_width=True):
                game.start_reveal()
                st.rerun()

        elif phase == "reveal":
            total, n = len(game.order), game.reveal_n
            btn = f"👀 Open next ticket ({n}/{total})" if n < total else "🏆 Show the winners"
            if st.button(btn, type="primary", use_container_width=True, key="host_reveal_next"):
                game.reveal_next()
                st.rerun()

        if phase != "write":
            if st.button("↩ Go back one round", use_container_width=True):
                game.back()
                st.rerun()

        st.divider()
        confirm = st.checkbox("I want to wipe everything and start a new game")
        if st.button("New game", disabled=not confirm, use_container_width=True):
            game.reset()
            st.session_state.pop("balloons_done", None)
            st.rerun()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.session_state["snap"] = game.snapshot()
header()

name_param = st.query_params.get("p", "")
if not name_param:
    st.markdown("### Who is playing?")
    with st.form("join_form"):
        name = st.text_input("Your name", max_chars=30, placeholder="e.g. Amina")
        go = st.form_submit_button("Join the game", type="primary", use_container_width=True)
    if go:
        if name.strip():
            st.query_params["p"] = " ".join(name.split())
            st.rerun()
        else:
            st.warning("Enter your name to join.")
    host_panel()
    st.stop()

my_key = game.join(name_param)
my_name = game.players[my_key]
is_host = bool(st.session_state.get("is_host"))

watcher()

phase = game.phase
if phase == "write":
    view_write(my_key)
elif phase == "answer":
    view_answer(my_key)
elif phase == "reveal":
    view_reveal(my_key, is_host)
else:
    view_final()

st.divider()
c1, c2 = st.columns([3, 1])
c1.caption(f"Playing as **{my_name}**")
if c2.button("Not you?", use_container_width=True):
    st.query_params.clear()
    st.rerun()

host_panel()

