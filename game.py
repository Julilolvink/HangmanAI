# hangman_app/app.py (top of file or in a separate module if you prefer)

import random
from dataclasses import dataclass, field
from typing import Set


@dataclass
class HangmanGame:
    """
    Simple Hangman game logic.

    This class is independent of Flask or any web stuff.
    It only knows about the game: word, guesses, etc.
    """
    secret_word: str
    max_attempts: int = 6
    guessed_letters: Set[str] = field(default_factory=set)
    wrong_guesses: int = 0
    finished: bool = False
    won: bool = False

    def guess(self, letter: str) -> None:
        """
        Process a player's letter guess.
        - 'letter' is expected to be a single alphabetical character.
        """
        if self.finished:
            # If the game is already over, ignore further guesses
            return

        letter = letter.lower()

        # Ignore guesses that are not a-z
        if not letter.isalpha() or len(letter) != 1:
            return

        # Ignore if we already guessed this letter
        if letter in self.guessed_letters:
            return

        # Record the guess
        self.guessed_letters.add(letter)

        if letter not in self.secret_word:
            # Wrong guess → increment counter
            self.wrong_guesses += 1
            if self.wrong_guesses >= self.max_attempts:
                # Player has run out of attempts → game lost
                self.finished = True
                self.won = False
        else:
            # Correct guess; check if this completes the word
            if all(ch in self.guessed_letters for ch in self.secret_word):
                self.finished = True
                self.won = True

    def masked_word(self) -> str:
        """
        Returns the secret word with unguessed letters replaced by underscores,
        e.g. 'c_t' for 'cat' with 'c' and 't' guessed.
        """
        return "".join(ch if ch in self.guessed_letters else "_" for ch in self.secret_word)

    def remaining_attempts(self) -> int:
        """
        How many wrong guesses are left.
        """
        return self.max_attempts - self.wrong_guesses

    def to_dict(self) -> dict:
        """
        Convert the game state to a dict so we can store it in Flask's session.
        (Flask session needs JSON-serializable data.)
        """
        return {
            "secret_word": self.secret_word,
            "max_attempts": self.max_attempts,
            "guessed_letters": list(self.guessed_letters),
            "wrong_guesses": self.wrong_guesses,
            "finished": self.finished,
            "won": self.won,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HangmanGame":
        """
        Recreate a HangmanGame object from a dict stored in the session.
        """
        return cls(
            secret_word=data["secret_word"],
            max_attempts=data["max_attempts"],
            guessed_letters=set(data["guessed_letters"]),
            wrong_guesses=data["wrong_guesses"],
            finished=data["finished"],
            won=data["won"],
        )
