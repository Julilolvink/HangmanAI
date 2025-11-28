# hangman_app/app.py

import os
import random
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, jsonify # type: ignore
from game import SinglePlayerGame, HumanPlayer, AIPlayer, VersusGame

# --- AI DIALOGUE TEMPLATES -------------------------------------------------- #

AI_START_LINES = [
    "Alright, let's see what you've got!",
    "A new game? I'm ready when you are.",
    "Time for a little mental workout.",
]

AI_LETTER_CORRECT_LINES = [
    "Hmm... I'll guess '{letter}'. Looks like I was right.",
    "Let's try '{letter}'. Nice, that fits!",
    "I'm thinking '{letter}'. Oh, that helped a lot.",
]

AI_LETTER_WRONG_LINES = [
    "How about '{letter}'? ...Oh, that was wrong.",
    "I'll go with '{letter}'. Huh, really? Not in there?",
    "Maybe '{letter}'? Oops, that didn't help.",
]

AI_SOLVE_LINES = [
    "Oh! I know! It's '{word}', isn't it!",
    "Everything lines up... The word must be '{word}'.",
    "Got it. Your word is '{word}'.",
]

AI_WIN_LINES = [
    "Looks like I win this one!",
    "Game over. Better luck next time!",
    "That was fun. I’ll take the victory.",
]

AI_LOSE_LINES = [
    "You got me this time. Well played!",
    "Nice! You solved it before I could.",
    "Okay, okay, you win. Good game!",
]

AI_PLAYER_GUESS_CORRECT_LINES = [
    "Nice guess, '{letter}' is in my word.",
    "Uh-oh, you found a letter with '{letter}'.",
    "You're getting closer with that '{letter}'.",
]

AI_PLAYER_GUESS_WRONG_LINES = [
    "Phew, safe. '{letter}' isn't in my word.",
    "Nope, not '{letter}'.",
    "Good try, but '{letter}' isn't there.",
]

# --- SIMPLE IN-MEMORY ROOM SYSTEM FOR PVP ----------------------------------- #

class GameRoom:
    """
    Represents a PVP room.

    - room_id: string chosen by the players (e.g. "1234")
    - players: dict[player_id -> HumanPlayer]
    - words: dict[player_id -> secret_word str or None]
    - game: VersusGame or None (before both words are set)
    - version: increments every time the room/game state changes

    """
    def __init__(self, room_id: str) -> None:
        self.room_id = room_id
        self.players: dict[str, HumanPlayer] = {}
        self.words: dict[str, str | None] = {}
        self.game: VersusGame | None = None
        self.version: int = 0  # <--- NEW

    def add_player(self, player: HumanPlayer) -> bool:
        """
        Try to add a player to the room.

        Returns:
        - True if the player was added (or already present).
        - False if room is full (more than 2 players).
        """
        if player.id in self.players:
            # Already in room
            return True

        if len(self.players) >= 2:
            # Room full
            return False

        self.players[player.id] = player
        # Initialize their word slot
        self.words[player.id] = None

        # Increment version on change
        self.version += 1

        return True

    def other_player(self, player_id: str) -> HumanPlayer | None:
        """
        Return the opponent of the player with player_id, if present.
        """
        for pid, p in self.players.items():
            if pid != player_id:
                return p
        return None

    def both_words_set(self) -> bool:
        """
        True if both players have provided a secret word.
        """
        if len(self.players) != 2:
            return False
        return all(
            (self.words.get(pid) is not None)
            for pid in self.players.keys()
        )

# Global in-memory room storage
ROOMS: dict[str, GameRoom] = {}

# --- PVP HELPER FUNCTIONS --------------------------------------------------- #

def get_or_create_room(room_id: str) -> GameRoom:
    """
    Get an existing GameRoom by its id, or create a new one if it doesn't exist.
    """
    room = ROOMS.get(room_id)
    if room is None:
        room = GameRoom(room_id)
        ROOMS[room_id] = room
    return room


def get_current_pvp_player() -> tuple[str, str]:
    """
    Ensure the current session has a PVP player id and name.

    Returns (player_id, player_name) from the session.
    """
    player_id = session.get("pvp_player_id")
    player_name = session.get("pvp_player_name", "Player")

    if player_id is None:
        # Create a new unique player id for this browser session
        player_id = f"pvp_{uuid.uuid4().hex[:8]}"
        session["pvp_player_id"] = player_id
        session["pvp_player_name"] = player_name

    return player_id, player_name


def set_current_pvp_player_name(name: str) -> None:
    """
    Update the stored name for the current PVP player in the session.
    """
    player_id, _ = get_current_pvp_player()
    clean_name = name.strip() or "Player"
    session["pvp_player_name"] = clean_name

app = Flask(__name__)

# Secret key is needed for sessions. In production, use a strong, secret value
# and store it in an environment variable.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "definitely-the-real-secret-key")


# --- WORD LIST SETUP --------------------------------------------------------- #

def load_words() -> list[str]:
    """
    Load a list of possible words for the game.

    For now:
    - Try to read from 'words.txt' if it exists.
    - Fallback to a small hardcoded list if not.

    Later you can replace this with a larger word list or a DB.
    """
    path = os.path.join(os.path.dirname(__file__), "words.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            # Strip whitespace and ignore empty lines
            return [line.strip().lower() for line in f if line.strip()]
    else:
        # Fallback: a few simple words
        return ["python", "flask", "azure", "hangman", "database", "object"]


WORDS = load_words()


def start_new_game() -> SinglePlayerGame:
    """
    Create a new SinglePlayerGame instance.

    For now, we hardcode a simple human player with id 'p1' and name 'You'.
    Later, when we add login, we can derive this from the user account.
    """
    player = HumanPlayer(player_id="p1", name="You")
    secret_word = random.choice(WORDS)
    game = SinglePlayerGame(player=player, secret_word=secret_word, max_attempts=6)
    return game


def save_game_to_session(game: SinglePlayerGame) -> None:
    """
    Store the current game's state in the Flask session.
    """
    session["singleplayer_game"] = game.to_dict()


def load_game_from_session() -> SinglePlayerGame | None:
    """
    Retrieve the game state from the Flask session, if it exists.
    """
    data = session.get("singleplayer_game")
    if not data:
        return None
    return SinglePlayerGame.from_dict(data)

# --- VERSUS AI GAME CREATION / SESSION HELPERS ------------------------------ #

def start_new_versus_ai_game(
    player_name: str,
    player_word: str,
    ai_intelligence: int,
) -> VersusGame:
    """
    Create a new VersusGame where:
    - Player 1 is the human
    - Player 2 is an AI with the chosen intelligence
    - The human's word is what the AI has to guess
    - The AI's word is chosen randomly from WORDS

    NOTE: In VersusGame:
    - word_for_player1 is owned by player1 (AI will guess it)
    - word_for_player2 is owned by player2 (human will guess it)
    """
    # Simple IDs for now; for real accounts we could tie to user id
    human = HumanPlayer(player_id="human1", name=player_name or "You")
    ai = AIPlayer(player_id="ai1", name="Computer", intelligence=ai_intelligence)

    # Normalize the human's chosen word
    player_word_clean = "".join(ch.lower() for ch in player_word if ch.isalpha())
    if not player_word_clean:
        # fallback to some default if user gave weird input
        player_word_clean = "default"

    # AI chooses its own word from the same word list
    ai_word = random.choice(WORDS)

    game = VersusGame(
        player1=human,
        player2=ai,
        word_for_player1=player_word_clean,
        word_for_player2=ai_word,
    )

    return game


def save_versus_ai_game_to_session(game: VersusGame) -> None:
    """
    Store the VersusGame (human vs AI) state in the session.
    """
    session["versus_ai_game"] = game.to_dict()


def load_versus_ai_game_from_session() -> VersusGame | None:
    """
    Reload the VersusGame (human vs AI) from the session.
    """
    data = session.get("versus_ai_game")
    if not data:
        return None
    return VersusGame.from_dict(data)

# --- ROUTES ------------------------------------------------------------------ #

@app.route("/")
def index():
    """
    Home menu: user can choose between singleplayer and (later) multiplayer.
    """
    return render_template("index.html")

@app.route("/single", methods=["GET", "POST"])
def singleplayer():
    """
    Singleplayer game view.
    This is exactly what your old "/" route was doing, just moved.
    """
    game = load_game_from_session()
    if game is None:
        game = start_new_game()
        save_game_to_session(game)

    if request.method == "POST":
        letter = request.form.get("letter", "").strip().lower()
        game.guess(letter)
        save_game_to_session(game)
        return redirect(url_for("singleplayer"))

    return render_template(
        "game.html",
        masked_word=game.masked_word(),
        wrong_guesses=game.wrong_guesses,
        remaining_attempts=game.remaining_attempts(),
        guessed_letters=sorted(game.guessed_letters),
        finished=game.finished,
        won=game.won,
        secret_word=game.secret_word if game.finished else None,
    )


@app.route("/single/new")
def new_singleplayer_game():
    """
    Start a new singleplayer game and redirect back to the singleplayer view.
    """
    game = start_new_game()
    save_game_to_session(game)
    return redirect(url_for("singleplayer"))

@app.route("/multiplayer")
def multiplayer_menu():
    """
    Multiplayer menu: choose between playing vs AI or (later) vs another player.
    """
    return render_template("multiplayer.html")

@app.route("/multiplayer/ai", methods=["GET", "POST"])
def multiplayer_ai_setup():
    """
    Setup page for playing vs AI.

    - GET: show form asking for player name, secret word, and AI intelligence.
    - POST: create a new VersusGame with those settings, store in session,
            then redirect to the actual game page.
    """
    if request.method == "POST":
        player_name = request.form.get("player_name", "").strip()
        player_word = request.form.get("player_word", "").strip()
        try:
            ai_intelligence = int(request.form.get("ai_intelligence", "50"))
        except ValueError:
            ai_intelligence = 50

        # Clamp AI intelligence to [0, 100]
        ai_intelligence = max(0, min(100, ai_intelligence))

        # Create and store game
        game = start_new_versus_ai_game(
            player_name=player_name,
            player_word=player_word,
            ai_intelligence=ai_intelligence,
        )
        save_versus_ai_game_to_session(game)

        session["ai_last_message"] = random.choice(AI_START_LINES)

        return redirect(url_for("multiplayer_ai_game"))

    return render_template("ai_setup.html")

@app.route("/multiplayer/ai/game", methods=["GET", "POST"])
def multiplayer_ai_game():
    """
    Actual VersusGame vs AI.

    - POST: process a human guess, save game, maybe set an AI losing line if the game ends.
    - GET: show current game state from the human's perspective.
           If it's AI's turn, the template will trigger an AI move after a delay.
    """
    game = load_versus_ai_game_from_session()
    if game is None:
        return redirect(url_for("multiplayer_ai_setup"))

    # Find the human and AI players
    human = None
    ai = None
    for p in game.players:
        if isinstance(p, HumanPlayer):
            human = p
        elif isinstance(p, AIPlayer):
            ai = p

    if human is None or ai is None:
        return redirect(url_for("multiplayer_ai_setup"))

    if request.method == "POST":
    # --- HUMAN TURN ---------------------------------------------------- #
        letter = request.form.get("letter", "").strip().lower()
        if letter:
            # Let the human attempt a guess and capture if it was correct
            was_correct = game.guess_letter(human, letter)

            # Decide what the AI says about this guess
            if game.finished and game.winner_id == human.id:
                # Human just won
                ai_line = random.choice(AI_LOSE_LINES)
            else:
                # Game continues, react to the correctness of the guess
                if was_correct:
                    template = random.choice(AI_PLAYER_GUESS_CORRECT_LINES)
                else:
                    template = random.choice(AI_PLAYER_GUESS_WRONG_LINES)
                ai_line = template.format(letter=letter)

            session["ai_last_message"] = ai_line

        save_versus_ai_game_to_session(game)
        return redirect(url_for("multiplayer_ai_game"))


    # ------------------------- GET branch --------------------------------- #

    # Prepare views for human and AI
    view_for_human = game.get_view_for(human)
    view_for_ai = game.get_view_for(ai)

    # Is it currently the AI's turn? (Two-player game => not human => AI)
    is_ai_turn = (not view_for_human["finished"]) and (not view_for_human["is_current_turn"])

    # AI's secret word (what the human is trying to guess)
    ai_secret_word = game.word_states_by_owner[ai.id].secret_word

    # Last AI message from the session (if any)
    ai_last_message = session.get("ai_last_message")

    return render_template(
        "ai_game.html",
        game_id=game.id,
        human_name=human.name,
        ai_name=ai.name,

        # Human's progress on AI's word:
        masked_word=view_for_human["masked_opponent_word"],
        guessed_letters=view_for_human["guessed_letters"],

        # AI's progress on human's word:
        ai_masked_word=view_for_ai["masked_opponent_word"],
        ai_guessed_letters=view_for_ai["guessed_letters"],

        # For losing feedback:
        ai_secret_word=ai_secret_word,

        # Turn and game state:
        is_current_turn=view_for_human["is_current_turn"],
        is_ai_turn=is_ai_turn,
        finished=view_for_human["finished"],
        winner_id=view_for_human["winner_id"],
        human_id=human.id,
        ai_id=ai.id,

        # AI dialogue:
        ai_last_message=ai_last_message,
    )

@app.route("/multiplayer/ai/move", methods=["POST"])
def multiplayer_ai_move():
    """
    Let the AI take exactly one move (letter guess or solve) with a small delay
    triggered from the frontend.

    This route:
    - Checks it's actually the AI's turn and the game isn't finished.
    - Asks the AI for a move.
    - Applies that move to the game.
    - Sets an appropriate AI dialogue line describing the action.
    """
    game = load_versus_ai_game_from_session()
    if game is None:
        return redirect(url_for("multiplayer_ai_setup"))

    # Find human and AI
    human = None
    ai = None
    for p in game.players:
        if isinstance(p, HumanPlayer):
            human = p
        elif isinstance(p, AIPlayer):
            ai = p

    if human is None or ai is None:
        return redirect(url_for("multiplayer_ai_setup"))

    # If the game is already finished, just go back
    if game.finished:
        return redirect(url_for("multiplayer_ai_game"))

    # It should be the AI's turn
    if not isinstance(game.get_current_player(), AIPlayer):
        return redirect(url_for("multiplayer_ai_game"))

    # Build view and let AI decide its move
    view_for_ai = game.get_view_for(ai)
    move = ai.decide_move(view_for_ai)
    move_type = move.get("type")

    # We'll build a line to store in session
    ai_line = None

    if move_type == "solve":
        # AI solves human's word
        # For the line we need the human's secret word
        human_word_state = game.word_states_by_owner[human.id]
        word = human_word_state.secret_word
        game.ai_solve_opponent_word(ai)

        # Pick a solve-style line
        template = random.choice(AI_SOLVE_LINES)
        ai_line = template.format(word=word)

    elif move_type == "letter":
        letter = move.get("letter", "")
        if letter:
            # Apply the guess; see if it was correct
            was_correct = game.guess_letter(ai, letter)

            if was_correct:
                template = random.choice(AI_LETTER_CORRECT_LINES)
            else:
                template = random.choice(AI_LETTER_WRONG_LINES)

            ai_line = template.format(letter=letter)
        else:
            # No valid letter - just do nothing
            ai_line = "Hmm... I'm not sure what to guess."

    else:
        # 'none' or unknown type
        ai_line = "I'll wait and see what you do next."

    # If the move ended the game and AI won, adjust the line
    if game.finished and game.winner_id == ai.id:
        if move_type == "solve":
            # Keep the solve line visible when AI wins by solving
            # (ai_line already contains the "I know! It's {word}" message)
            pass
        else:
            # For a win by regular letter guessing, use a generic win line
            ai_line = random.choice(AI_WIN_LINES)

    # Store last AI message
    session["ai_last_message"] = ai_line

    save_versus_ai_game_to_session(game)
    return redirect(url_for("multiplayer_ai_game"))

@app.route("/multiplayer/pvp", methods=["GET", "POST"])
def pvp_join():
    """
    Page where the user can enter their name and a room id to join.

    - GET: show the form.
    - POST: process the form and put the player into a room.
    """
    error = None

    if request.method == "POST":
        name = request.form.get("player_name", "").strip()
        room_id = request.form.get("room_id", "").strip()

        if not room_id:
            error = "Please enter a room number."
        else:
            # Ensure we have a player id in session
            player_id, _ = get_current_pvp_player()
            if name:
                set_current_pvp_player_name(name)
            player_name = session.get("pvp_player_name", "Player")

            # Create a HumanPlayer object for the room
            human = HumanPlayer(player_id=player_id, name=player_name)

            room = get_or_create_room(room_id)

            if not room.add_player(human):
                # Room is full and this player isn't already in it
                error = f"Room {room_id} is already full (2 players)."
            else:
                # Successfully joined
                return redirect(url_for("pvp_room", room_id=room_id))

    return render_template("pvp_join.html", error=error)

@app.route("/multiplayer/pvp/room/<room_id>", methods=["GET"])
def pvp_room(room_id: str):
    """
    Main PVP room view.

    Depending on the state, this shows:
    - Waiting for opponent
    - Choose your secret word
    - Waiting for opponent to choose their word
    - Active VersusGame (PVP)
    """
    room = ROOMS.get(room_id)
    if room is None:
        # Room doesn't exist or was cleared
        return redirect(url_for("pvp_join"))

    # Identify current player from session
    player_id, player_name = get_current_pvp_player()
    player = room.players.get(player_id)

    if player is None:
        # User not in this room; redirect to join page
        return redirect(url_for("pvp_join"))

    # Opponent (if present)
    opponent = room.other_player(player_id)
    opponent_name = opponent.name if opponent else None

    # 1) Only one player in room -> waiting for opponent
    if len(room.players) < 2:
        return render_template(
            "pvp_room.html",
            room_id=room_id,
            mode="waiting_for_opponent",
            player_name=player.name,
            opponent_name=opponent_name,
            current_version=room.version,
        )

    # From here on, we know we have 2 players in the room
    # 2) No game yet -> we are in the "word choosing" phase
    if room.game is None:
        my_word = room.words.get(player_id)
        other_player = room.other_player(player_id)
        other_word = room.words.get(other_player.id) if other_player else None

        if my_word is None:
            # This player still needs to choose their word
            return render_template(
                "pvp_room.html",
                room_id=room_id,
                mode="choose_word",
                player_name=player.name,
                opponent_name=opponent_name,
                current_version=room.version,

            )
        elif other_word is None:
            # This player has chosen; waiting for the opponent
            return render_template(
                "pvp_room.html",
                room_id=room_id,
                mode="waiting_for_other_word",
                player_name=player.name,
                opponent_name=opponent_name,
                current_version=room.version,

            )
        else:
            # Both words are set; create VersusGame and redirect so the
            # next visit falls into "in_game" branch
            players_list = list(room.players.values())
            p1 = players_list[0]
            p2 = players_list[1]
            word_for_p1 = room.words[p1.id]
            word_for_p2 = room.words[p2.id]

            room.game = VersusGame(
                player1=p1,
                player2=p2,
                word_for_player1=word_for_p1,
                word_for_player2=word_for_p2,
            )
            return redirect(url_for("pvp_room", room_id=room_id))

    # 3) Active or finished game
    game = room.game
    assert game is not None

    # Build views for the current player and opponent
    view_for_me = game.get_view_for(player)
    view_for_opp = game.get_view_for(room.other_player(player_id))

    # For the template:
    # - The word I'm trying to guess is the opponent's word (masked)
    # - The word they're trying to guess is mine (masked from their view)
    my_id = player.id
    opp_id = room.other_player(player_id).id

    return render_template(
        "pvp_room.html",
        room_id=room_id,
        mode="in_game" if not view_for_me["finished"] else "finished",
        player_name=player.name,
        opponent_name=opponent_name,

        # My view on opponent's word
        masked_word=view_for_me["masked_opponent_word"],
        guessed_letters=view_for_me["guessed_letters"],
        is_current_turn=view_for_me["is_current_turn"],

        # Opponent's progress on my word
        opp_masked_word=view_for_opp["masked_opponent_word"],
        opp_guessed_letters=view_for_opp["guessed_letters"],

        finished=view_for_me["finished"],
        winner_id=view_for_me["winner_id"],
        my_id=my_id,
        opp_id=opp_id,

        current_version=room.version,
    )

@app.route("/multiplayer/pvp/room/<room_id>/word", methods=["POST"])
def pvp_submit_word(room_id: str):
    """
    Handle submission of the player's secret word in PVP.
    """
    room = ROOMS.get(room_id)
    if room is None:
        return redirect(url_for("pvp_join"))

    player_id, _ = get_current_pvp_player()
    if player_id not in room.players:
        return redirect(url_for("pvp_join"))

    word_raw = request.form.get("player_word", "").strip().lower()
    # Keep only alphabetic characters
    word_clean = "".join(ch for ch in word_raw if ch.isalpha())

    if not word_clean:
        # Just ignore and reload; could add error flash later
        return redirect(url_for("pvp_room", room_id=room_id))

    room.words[player_id] = word_clean
    room.version += 1  # word changed -> version++


    # If both words are now set and there's no game yet, create it
    if room.game is None and room.both_words_set():
        players_list = list(room.players.values())
        p1 = players_list[0]
        p2 = players_list[1]
        word_for_p1 = room.words[p1.id]
        word_for_p2 = room.words[p2.id]

        room.game = VersusGame(
            player1=p1,
            player2=p2,
            word_for_player1=word_for_p1,
            word_for_player2=word_for_p2,
        )
        room.version += 1  # game created -> version++

    return redirect(url_for("pvp_room", room_id=room_id))

@app.route("/multiplayer/pvp/room/<room_id>/guess", methods=["POST"])
def pvp_guess(room_id: str):
    """
    Handle a letter guess from the current player in a PVP VersusGame.
    """
    room = ROOMS.get(room_id)
    if room is None or room.game is None:
        return redirect(url_for("pvp_room", room_id=room_id))

    game = room.game
    player_id, _ = get_current_pvp_player()
    player = room.players.get(player_id)
    if player is None:
        return redirect(url_for("pvp_join"))

    letter = request.form.get("letter", "").strip().lower()
    if letter:
        game.guess_letter(player, letter)
        room.version += 1  # game state changed -> version++

    # No AI here, so we just apply the guess and redirect back to the room
    return redirect(url_for("pvp_room", room_id=room_id))

@app.route("/multiplayer/pvp/room/<room_id>/state", methods=["GET"])
def pvp_room_state(room_id: str):
    """
    Lightweight JSON endpoint for polling the state of a PVP room.

    The client can use this to detect changes (via the version field)
    and decide when to reload the page.
    """
    room = ROOMS.get(room_id)
    if room is None:
        return jsonify({"error": "room_not_found"}), 404

    # Identify current player
    player_id, _ = get_current_pvp_player()
    player = room.players.get(player_id)

    if player is None:
        return jsonify({"error": "not_in_room"}), 403

    # Determine mode, similar to pvp_room
    if len(room.players) < 2:
        mode = "waiting_for_opponent"
        is_current_turn = False
        finished = False
        winner_id = None

    elif room.game is None:
        # Word choosing phase
        my_word = room.words.get(player_id)
        other_player = room.other_player(player_id)
        other_word = room.words.get(other_player.id) if other_player else None

        if my_word is None:
            mode = "choose_word"
        elif other_word is None:
            mode = "waiting_for_other_word"
        else:
            # Both words set, but game not yet created - rare race situation
            mode = "creating_game"

        is_current_turn = False
        finished = False
        winner_id = None

    else:
        # Active or finished game
        game = room.game
        view_for_me = game.get_view_for(player)
        mode = "in_game"
        if view_for_me["finished"]:
            mode = "finished"
        is_current_turn = view_for_me["is_current_turn"]
        finished = view_for_me["finished"]
        winner_id = view_for_me["winner_id"]

    return jsonify(
        {
            "version": room.version,
            "mode": mode,
            "is_current_turn": is_current_turn,
            "finished": finished,
            "winner_id": winner_id,
        }
    )


if __name__ == "__main__":
    # Local development entrypoint.
    # In Azure you'll usually run via gunicorn instead.
    app.run(debug=True)
