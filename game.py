# hangman_app/app.py (top of file or in a separate module if you prefer)

import random
import uuid
from dataclasses import dataclass, field
from typing import List, Set, Optional

class Player:
    """
    Base player class.

    Later we'll also have AIPlayer inheriting from this.
    For now, it's just a simple container for id + name.
    """
    def __init__(self, player_id: str, name: str) -> None:
        self.id = player_id
        self.name = name

class HumanPlayer(Player):
    """
    Human-controlled player.

    We'll extend this later if we add accounts, stats, etc.
    For now it is identical to Player, but kept as a separate type
    so that VersusGame can easily distinguish between human and AI players.
    """
    pass

class HangmanGame:
    """
    Base class for any Hangman-style game.

    For now, we only store very generic information here:
    - A unique game id
    - A list of players
    - Finished flag
    - Winner id (if any)

    SinglePlayerGame and future VersusGame will extend this.
    """
    def __init__(self, players: List[Player]) -> None:
        # Assign a random unique id to this game instance
        self.id: str = str(uuid.uuid4())
        self.players: List[Player] = players
        self.finished: bool = False
        self.winner_id: Optional[str] = None

class SinglePlayerGame(HangmanGame):
    """
    Single-player hangman game.

    This is essentially your old HangmanGame, but now:
    - It inherits from HangmanGame (base class)
    - It has an explicit HumanPlayer object
    """
    def __init__(self, player: HumanPlayer, secret_word: str, max_attempts: int = 6) -> None:
        # Initialize base class with a single player
        super().__init__([player])

        # Keep a direct reference to the single player for convenience
        self.player: HumanPlayer = player

        # Game-specific fields (same as your previous HangmanGame)
        self.secret_word: str = secret_word.lower()
        self.max_attempts: int = max_attempts
        self.guessed_letters: Set[str] = set()
        self.wrong_guesses: int = 0
        self.won: bool = False

    def guess(self, letter: str) -> None:
        """
        Process a player's letter guess.
        Behaviour is identical to your old single-player HangmanGame.
        """
        if self.finished:
            return

        letter = letter.lower()

        if not letter.isalpha() or len(letter) != 1:
            # Ignore invalid guesses
            return

        if letter in self.guessed_letters:
            # Ignore repeated guesses
            return

        self.guessed_letters.add(letter)

        if letter not in self.secret_word:
            # Wrong guess
            self.wrong_guesses += 1
            if self.wrong_guesses >= self.max_attempts:
                self.finished = True
                self.won = False
                self.winner_id = None  # no winner in this case
        else:
            # Correct guess – check if the whole word is now revealed
            if all(ch in self.guessed_letters for ch in self.secret_word):
                self.finished = True
                self.won = True
                self.winner_id = self.player.id

    def masked_word(self) -> str:
        """
        Returns the secret word with unguessed letters replaced by underscores.
        Example: 'cat' -> 'c_t' if 'c' and 't' have been guessed.
        """
        return "".join(ch if ch in self.guessed_letters else "_" for ch in self.secret_word)

    def remaining_attempts(self) -> int:
        """
        Returns how many wrong guesses are left.
        """
        return self.max_attempts - self.wrong_guesses

    def to_dict(self) -> dict:
        """
        Convert the game state to a dict for storing in the Flask session.

        We include:
        - Game id
        - Player info
        - Secret word & guesses
        - Basic status flags
        """
        return {
            "id": self.id,
            "player": {
                "id": self.player.id,
                "name": self.player.name,
            },
            "secret_word": self.secret_word,
            "max_attempts": self.max_attempts,
            "guessed_letters": list(self.guessed_letters),
            "wrong_guesses": self.wrong_guesses,
            "finished": self.finished,
            "won": self.won,
            "winner_id": self.winner_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SinglePlayerGame":
        """
        Recreate a SinglePlayerGame object from a dict stored in the session.

        Note:
        - We call the regular constructor, then overwrite some fields
          so we don't have to reimplement all setup logic manually.
        """
        # Rebuild the player first
        player_data = data["player"]
        player = HumanPlayer(player_id=player_data["id"], name=player_data["name"])

        # Create a fresh game instance
        game = cls(
            player=player,
            secret_word=data["secret_word"],
            max_attempts=data["max_attempts"],
        )

        # Overwrite state fields with values from the dict
        game.id = data["id"]
        game.guessed_letters = set(data["guessed_letters"])
        game.wrong_guesses = data["wrong_guesses"]
        game.finished = data["finished"]
        game.won = data["won"]
        game.winner_id = data["winner_id"]

        return game