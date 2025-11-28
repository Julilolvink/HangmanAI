# hangman_app/app.py

import os
import random
from flask import Flask, render_template, request, redirect, url_for, session

from game import HangmanGame

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


def start_new_game() -> HangmanGame:
    """
    Create a new HangmanGame with a random word from WORDS.
    """
    secret_word = random.choice(WORDS)
    return HangmanGame(secret_word=secret_word, max_attempts=6)


def save_game_to_session(game: HangmanGame) -> None:
    """
    Store the game state in the Flask session.
    We store it as a dict because the session is JSON-serialized.
    """
    session["game"] = game.to_dict()


def load_game_from_session() -> HangmanGame | None:
    """
    Retrieve the game state from the session, if it exists.
    """
    data = session.get("game")
    if not data:
        return None
    return HangmanGame.from_dict(data)


# --- ROUTES ------------------------------------------------------------------ #

@app.route("/", methods=["GET", "POST"])
def game_view():
    """
    Main route for the game.
    - GET: show current game or start a new one if none exists.
    - POST: process a letter guess from the user.
    """
    game = load_game_from_session()
    if game is None:
        # No game in session yet -> start a new one
        game = start_new_game()
        save_game_to_session(game)

    if request.method == "POST":
        # Read the 'letter' field from the submitted form
        letter = request.form.get("letter", "").strip().lower()
        # Perform the guess in the game object
        game.guess(letter)
        # Save updated game back to the session
        save_game_to_session(game)
        # Redirect to avoid form resubmit on refresh (Post/Redirect/Get pattern)
        return redirect(url_for("game_view"))

    # For GET requests, render the template with the current game state
    return render_template(
        "index.html",
        masked_word=game.masked_word(),
        wrong_guesses=game.wrong_guesses,
        remaining_attempts=game.remaining_attempts(),
        guessed_letters=sorted(game.guessed_letters),
        finished=game.finished,
        won=game.won,
        secret_word=game.secret_word if game.finished else None,
    )


@app.route("/new")
def new_game():
    """
    Start a brand new game and redirect to the main game view.
    """
    game = start_new_game()
    save_game_to_session(game)
    return redirect(url_for("game_view"))


if __name__ == "__main__":
    # Local development entrypoint.
    # In Azure you'll usually run via gunicorn instead.
    app.run(debug=True)
