# hangman_app/app.py

import os
import random
from flask import Flask, render_template, request, redirect, url_for, session # type: ignore
from game import SinglePlayerGame, HumanPlayer, AIPlayer, VersusGame



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

        return redirect(url_for("multiplayer_ai_game"))

    return render_template("ai_setup.html")

@app.route("/multiplayer/ai/game", methods=["GET", "POST"])
def multiplayer_ai_game():
    """
    Actual VersusGame vs AI.

    - GET: show current game state from the human's perspective.
    - POST: process a human guess, then let the AI take its turn(s), then redirect.
    """
    game = load_versus_ai_game_from_session()
    if game is None:
        # If somehow no game in session, go back to AI setup
        return redirect(url_for("multiplayer_ai_setup"))

    # Find the human and AI players in this game
    human = None
    ai = None
    for p in game.players:
        if isinstance(p, HumanPlayer):
            human = p
        elif isinstance(p, AIPlayer):
            ai = p

    if human is None or ai is None:
        # If something is wrong with player types, reset to setup
        return redirect(url_for("multiplayer_ai_setup"))

    if request.method == "POST":
        # --- HUMAN TURN ---------------------------------------------------- #
        letter = request.form.get("letter", "").strip().lower()
        if letter:
            # Let the human attempt a guess
            game.guess_letter(human, letter)

        # --- AI TURN(S) ---------------------------------------------------- #
        # After the human's move, it's possible that:
        # - The game has ended (human won).
        # - It is still the human's turn (correct guess).
        # - It is now the AI's turn (wrong guess, or we add timeout logic later).

        while (not game.finished) and isinstance(game.get_current_player(), AIPlayer):
            # Build a view for the AI
            view_for_ai = game.get_view_for(ai)
            move = ai.decide_move(view_for_ai)

            move_type = move.get("type")
            if move_type == "solve":
                game.ai_solve_opponent_word(ai)
                break
            elif move_type == "letter":
                letter_to_guess = move.get("letter", "")
                if letter_to_guess:
                    game.guess_letter(ai, letter_to_guess)
                else:
                    break
            else:
                # "none" or unknown -> stop AI loop
                break

        # Save updated game state and redirect (Post/Redirect/Get)
        save_versus_ai_game_to_session(game)
        return redirect(url_for("multiplayer_ai_game"))

    # ------------------------- GET branch --------------------------------- #
    # If it's the AI's turn when the page loads, let the AI play immediately
    if (not game.finished) and isinstance(game.get_current_player(), AIPlayer):
        while (not game.finished) and isinstance(game.get_current_player(), AIPlayer):
            view_for_ai = game.get_view_for(ai)
            move = ai.decide_move(view_for_ai)

            move_type = move.get("type")
            if move_type == "solve":
                game.ai_solve_opponent_word(ai)
                break
            elif move_type == "letter":
                letter_to_guess = move.get("letter", "")
                if letter_to_guess:
                    game.guess_letter(ai, letter_to_guess)
                else:
                    break
            else:
                break

        save_versus_ai_game_to_session(game)
        # After AI moves, we continue to render the updated state below

    # For GET: prepare view for the human and AI
    view_for_human = game.get_view_for(human)
    view_for_ai = game.get_view_for(ai)

    # The word you (the human) are trying to guess is the AI's word,
    # which is stored in the WordState owned by the AI player.
    ai_secret_word = game.word_states_by_owner[ai.id].secret_word


    # Additionally, we can show AI's guessed letters and maybe how much of
    # the player's word is revealed. But we will keep it simple for now.
    # We'll show:
    # - Word the human is trying to guess (AI's word), masked
    # - Whose turn it is
    # - Basic end-of-game result

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

        # New: full AI word (we'll only show it on loss)
        ai_secret_word=ai_secret_word,

        is_current_turn=view_for_human["is_current_turn"],
        finished=view_for_human["finished"],
        winner_id=view_for_human["winner_id"],
        human_id=human.id,
        ai_id=ai.id,
    )


if __name__ == "__main__":
    # Local development entrypoint.
    # In Azure you'll usually run via gunicorn instead.
    app.run(debug=True)
