# hangman_app/app.py

import os
import random
from flask import Flask, render_template, request, redirect, url_for, session
from game import SinglePlayerGame, HumanPlayer  # <-- updated import


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


if __name__ == "__main__":
    # Local development entrypoint.
    # In Azure you'll usually run via gunicorn instead.
    app.run(debug=True)
