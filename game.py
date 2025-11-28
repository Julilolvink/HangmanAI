# hangman_app/app.py (top of file or in a separate module if you prefer)

import random
import uuid
import time
from typing import List, Set, Optional

# Approximate letter frequencies in English (relative usage)
LETTER_FREQUENCIES = {
    "e": 0.126621,
    "t": 0.090728,
    "a": 0.081756,
    "o": 0.074777,
    "i": 0.069791,
    "n": 0.066803,
    "s": 0.062812,
    "h": 0.060916,
    "r": 0.059821,
    "d": 0.042871,
    "l": 0.039880,
    "c": 0.027918,
    "u": 0.027918,
    "m": 0.023929,
    "w": 0.023929,
    "f": 0.021934,
    "g": 0.019940,
    "y": 0.019940,
    "p": 0.018947,
    "b": 0.014958,
    "v": 0.009970,
    "k": 0.007976,
    "j": 0.001994,
    "x": 0.001994,
    "q": 0.000998,
    "z": 0.000998,
}


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

class AIPlayer(Player):
    """
    AI-controlled player.

    The important property here is 'intelligence':
    - 0   = extremely dumb, almost completely random guesses
    - 50  = average, partially guided by letter frequency
    - 100 = very smart, heavily guided by letter frequency and can
            "recognize" the word earlier

    This class does NOT directly modify the game. It only decides
    what move it *wants* to make, based on a 'view' of the game.
    The game (VersusGame) remains responsible for actually applying
    that move and updating state.
    """

    def __init__(self, player_id: str, name: str, intelligence: int) -> None:
        super().__init__(player_id=player_id, name=name)
        # Clamp intelligence to [0, 100] to avoid weird values
        self.intelligence: int = max(0, min(100, intelligence))

    def decide_move(self, game_view: dict) -> dict:
        """
        Decide what move to make based on the provided 'game_view'.

        The view is expected to look like what VersusGame.get_view_for(...) returns:
        {
            "game_id": ...,
            "player_id": ...,
            "player_name": ...,
            "opponent_name": ...,
            "masked_opponent_word": "...",
            "guessed_letters": [...],
            "is_current_turn": bool,
            "finished": bool,
            "winner_id": ...
        }

        This method returns a dict describing the AI's chosen move:

        - {"type": "solve"}
            -> The AI claims to know the full word and wants to solve it.
               The game will then reveal the entire word and declare the AI winner.

        - {"type": "letter", "letter": "e"}
            -> The AI wants to guess the single letter 'e'.

        The caller (VersusGame or higher-level code) is responsible for:
        - Checking that it's actually the AI's turn.
        - Applying the move via guess_letter(...) or ai_solve_opponent_word(...).
        """
        # If the game is already finished, no move to make
        if game_view.get("finished"):
            return {"type": "none"}

        # If it's not our turn, also do nothing
        if not game_view.get("is_current_turn", False):
            return {"type": "none"}

        masked_word: str = game_view["masked_opponent_word"]
        guessed_letters = set(game_view["guessed_letters"])

        # First, see if we "recognize" the word
        if self._should_attempt_solve(masked_word, guessed_letters):
            # We don't need to know the actual word here; the game will
            # handle revealing it when it sees this "solve" decision.
            return {"type": "solve"}

        # Otherwise, we guess a single letter
        letter = self._choose_letter(masked_word, guessed_letters)
        return {"type": "letter", "letter": letter}

    # ------------------------------------------------------------------ #
    # Internal helper methods
    # ------------------------------------------------------------------ #

    def _should_attempt_solve(
        self,
        masked_word: str,
        guessed_letters: set[str],
    ) -> bool:
        """
        Decide whether the AI believes it can recognize the word.

        We use a rough heuristic:
        - Compute the fraction of revealed letters (non-underscore chars).
        - Combine that with the AI's intelligence to form a probability.
        - Draw a random number; if it's lower than that probability, we "solve".

        Formula idea inspired by your suggestion:

        p = (revealed_ratio) ^ (11 - intelligence / 10)

        - For low intelligence, exponent is high (e.g., 11), making p quite small
          until the word is almost complete.
        - For high intelligence, exponent is lower, so p grows faster as letters
          are revealed.

        We also ensure the word has at least 1 revealed letter before considering
        a solve attempt.
        """
        # Count letters in the word and how many are revealed
        length = len(masked_word)
        if length == 0:
            return False

        revealed_count = sum(1 for ch in masked_word if ch != "_")
        if revealed_count == 0:
            # If we see nothing, we can't possibly "recognize" the word
            return False

        revealed_ratio = revealed_count / length

        # Map intelligence [0, 100] -> exponent between about 11 and 1
        exponent = max(1.0, 11.0 - self.intelligence / 10.0)

        recognition_probability = revealed_ratio ** exponent

        # Draw random number in [0, 1)
        r = random.random()
        return r < recognition_probability

    def _choose_letter(self, masked_word: str, guessed_letters: set[str]) -> str:
        """
        Choose a letter to guess.

        Strategy:
        - Consider all letters a-z that have NOT been guessed yet.
        - Use a blend of:
            * uniform random choice
            * English letter-frequency-based weighted choice
          The blend factor depends on intelligence:
            - intelligence 0  -> almost pure uniform random
            - intelligence 50 -> roughly equal blend
            - intelligence 100 -> almost pure frequency-based choice

        This means smarter AIs are more likely to pick 'e', 't', 'a', etc.
        """
        all_letters = set("abcdefghijklmnopqrstuvwxyz")
        remaining_letters = sorted(all_letters - guessed_letters)

        # If somehow no letters remain (should be rare), just fallback to 'e'
        if not remaining_letters:
            return "e"

        # Intelligence in [0, 1] as a blending factor
        mix = self.intelligence / 100.0

        # Build probability distribution over remaining letters
        # based on a blend of uniform and frequency weights.
        n = len(remaining_letters)
        uniform_prob = 1.0 / n

        # Normalize frequencies over remaining letters
        freq_values = []
        for ch in remaining_letters:
            freq_values.append(LETTER_FREQUENCIES.get(ch, 0.001))  # tiny default for unknown

        total_freq = sum(freq_values)
        if total_freq <= 0:
            # If something goes wrong, fallback to uniform random
            return random.choice(remaining_letters)

        normalized_freqs = [fv / total_freq for fv in freq_values]

        # Blend uniform + frequency-based probabilities
        probabilities: list[float] = []
        for i in range(n):
            p_uniform = uniform_prob
            p_freq = normalized_freqs[i]
            p = (1.0 - mix) * p_uniform + mix * p_freq
            probabilities.append(p)

        # Sample a letter according to the probabilities
        # We build a cumulative distribution and draw a random number.
        r = random.random()
        cumulative = 0.0
        for ch, p in zip(remaining_letters, probabilities):
            cumulative += p
            if r <= cumulative:
                return ch

        # Fallback in case of floating point issues
        return remaining_letters[-1]

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

class WordState:
    """
    Represents the state of a single secret word in a hangman-style game.

    This is used in VersusGame so that each player can have their own word
    that the opponent is trying to guess.

    It stores:
    - The secret word
    - The letters that have been guessed so far

    It does NOT track attempts or whose turn it is; that's the job of the game.
    """

    def __init__(self, secret_word: str) -> None:
        # Normalize the secret word to lowercase
        self.secret_word: str = secret_word.lower()
        # Letters that have been guessed so far (both correct and wrong)
        self.guessed_letters: Set[str] = set()

    def apply_guess(self, letter: str) -> bool:
        """
        Apply a letter guess to this word.

        Returns:
        - True if the guess was valid & the letter is in the secret word
        - False if the guess was valid but the letter is NOT in the word

        If the letter is invalid (non-alpha, >1 char) or already guessed,
        the method does nothing and returns False.

        NOTE: The game (VersusGame) will decide what to do when a guess is repeated
        or invalid; here we just provide a simple boolean.
        """
        letter = letter.lower()

        # Basic validation
        if not letter.isalpha() or len(letter) != 1:
            return False

        # If we've already guessed this letter, ignore
        if letter in self.guessed_letters:
            return False

        self.guessed_letters.add(letter)
        return letter in self.secret_word

    def masked_word(self) -> str:
        """
        Returns the word with unguessed letters replaced by underscores.
        """
        return "".join(
            ch if ch in self.guessed_letters else "_"
            for ch in self.secret_word
        )

    def is_fully_revealed(self) -> bool:
        """
        Returns True if all letters in the secret word have been guessed.
        """
        return all(ch in self.guessed_letters for ch in self.secret_word)

    def to_dict(self) -> dict:
        """
        Convert this WordState to a dict so it can be serialized (e.g. into session).
        """
        return {
            "secret_word": self.secret_word,
            "guessed_letters": list(self.guessed_letters),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WordState":
        """
        Rebuild a WordState from a serialized dict.
        """
        ws = cls(secret_word=data["secret_word"])
        ws.guessed_letters = set(data["guessed_letters"])
        return ws

class VersusGame(HangmanGame):
    """
    Two-player hangman-style game.

    Each player chooses a secret word. During the game:
    - On their turn, a player guesses letters in the *opponent's* word.
    - If they guess a letter correctly, they get another turn.
    - If they guess incorrectly, the turn switches to the other player.
    - When a player reveals the final letter of the opponent's word,
      they win the game.

    There is no fixed limit on the number of wrong guesses.

    This class only contains the core rules; it does NOT know about HTTP, Flask,
    or how players submit their guesses.
    """

    def __init__(
        self,
        player1: Player,
        player2: Player,
        word_for_player1: str,
        word_for_player2: str,
    ) -> None:
        # Initialize the base class with both players
        super().__init__([player1, player2])

        # Map from "owner player id" -> WordState for that player's word
        # Example: word_states_by_owner[player1.id] is the word the second player is guessing.
        self.word_states_by_owner: dict[str, WordState] = {
            player1.id: WordState(word_for_player1),
            player2.id: WordState(word_for_player2),
        }

        # Index (0 or 1) into self.players for whose turn it is
        self.current_player_index: int = random.choice([0, 1])

        # Track when the current turn started (for timeouts later)
        self.turn_started_at: float = time.time()

    # --------------------------------------------------------------------- #
    # Core gameplay methods
    # --------------------------------------------------------------------- #

    def get_current_player(self) -> Player:
        """
        Returns the Player whose turn it currently is.
        """
        return self.players[self.current_player_index]

    def get_opponent_of(self, player: Player) -> Player:
        """
        Given a player, return their opponent in this 2-player game.
        """
        if len(self.players) != 2:
            raise ValueError("VersusGame expects exactly 2 players.")

        if player.id == self.players[0].id:
            return self.players[1]
        elif player.id == self.players[1].id:
            return self.players[0]
        else:
            raise ValueError("Player is not part of this game.")

    def guess_letter(self, player: Player, letter: str) -> bool:
        """
        Apply a letter guess on behalf of 'player'.

        Returns:
        - True if the guess was a *valid guess* and the letter is in the opponent's word.
        - False otherwise (wrong letter or invalid/repeated guess).

        Logic:
        - If it's not this player's turn, the guess is ignored and returns False.
        - We apply the guess to the opponent's WordState.
        - If the opponent's word becomes fully revealed, 'player' wins.
        - If the guess is wrong, turn switches to the opponent.
        - If the guess is correct, the same player keeps the turn.
        """
        if self.finished:
            return False

        # Only allow the current player to guess
        current_player = self.get_current_player()
        if player.id != current_player.id:
            # Not this player's turn; ignore the guess
            return False

        opponent = self.get_opponent_of(player)
        opponent_word_state = self.word_states_by_owner[opponent.id]

        # Apply guess to opponent's word
        was_correct = opponent_word_state.apply_guess(letter)

        if opponent_word_state.is_fully_revealed():
            # Current player has revealed the entire word
            self.finished = True
            self.winner_id = player.id
            return was_correct

        if not was_correct:
            # Wrong guess -> switch turn to opponent
            self._switch_turn()

        # If correct, the same player keeps the turn
        return was_correct
    
    def ai_solve_opponent_word(self, player: Player) -> None:
        """
        Let 'player' correctly solve the opponent's word in one go.

        This is used when an AI has "recognized" the word.

        Effect:
        - All letters in the opponent's secret word are considered guessed.
        - The game is immediately finished with 'player' as the winner.
        """
        if self.finished:
            return

        current_player = self.get_current_player()
        if player.id != current_player.id:
            # Only the current player is allowed to solve
            return

        opponent = self.get_opponent_of(player)
        opponent_word_state = self.word_states_by_owner[opponent.id]

        # Reveal all letters in the opponent's word
        for ch in opponent_word_state.secret_word:
            opponent_word_state.guessed_letters.add(ch)

        # Mark game as finished and record winner
        self.finished = True
        self.winner_id = player.id    

    def _switch_turn(self) -> None:
        """
        Switch control to the other player and reset the turn timer.
        """
        self.current_player_index = 1 - self.current_player_index
        self.turn_started_at = time.time()

    # --------------------------------------------------------------------- #
    # Timeout logic
    # --------------------------------------------------------------------- #

    def check_timeout(self, now: float, timeout_seconds: float) -> bool:
        """
        Check if the current player's turn has timed out.

        If the time since 'turn_started_at' exceeds 'timeout_seconds'
        and the game is not finished:
        - The turn is given to the opponent.
        - 'turn_started_at' is updated.
        - Returns True to indicate a timeout occurred.

        If no timeout occurs, returns False.
        """
        if self.finished:
            return False

        if now - self.turn_started_at >= timeout_seconds:
            self._switch_turn()
            return True

        return False

    # --------------------------------------------------------------------- #
    # View / serialization helpers
    # --------------------------------------------------------------------- #

    def get_view_for(self, player: Player) -> dict:
        """
        Build a simplified 'view' of the game for the given player.

        This is what a UI or AI would need to know:
        - Their own id and name
        - Opponent's name
        - The masked version of the opponent's word
        - Letters already guessed in the opponent's word
        - Whose turn it is
        - Whether the game is finished and who won
        """
        opponent = self.get_opponent_of(player)
        opponent_word_state = self.word_states_by_owner[opponent.id]

        return {
            "game_id": self.id,
            "player_id": player.id,
            "player_name": player.name,
            "opponent_name": opponent.name,
            "masked_opponent_word": opponent_word_state.masked_word(),
            "guessed_letters": sorted(opponent_word_state.guessed_letters),
            "is_current_turn": (self.get_current_player().id == player.id),
            "finished": self.finished,
            "winner_id": self.winner_id,
        }

    def to_dict(self) -> dict:
        """
        Serialize the VersusGame into a dict so it can be stored (e.g. in session).

        We store:
        - Game id
        - Players (with type info: human or ai, and AI intelligence if applicable)
        - Word states for each owner
        - Current turn index
        - Finished flag & winner
        - Turn start time (for timeouts)
        """
        players_data = []
        for p in self.players:
            base = {
                "id": p.id,
                "name": p.name,
            }
            if isinstance(p, AIPlayer):
                base["type"] = "ai"
                base["intelligence"] = p.intelligence
            elif isinstance(p, HumanPlayer):
                base["type"] = "human"
            else:
                base["type"] = "generic"
            players_data.append(base)

        return {
            "id": self.id,
            "players": players_data,
            "word_states_by_owner": {
                owner_id: ws.to_dict()
                for owner_id, ws in self.word_states_by_owner.items()
            },
            "current_player_index": self.current_player_index,
            "finished": self.finished,
            "winner_id": self.winner_id,
            "turn_started_at": self.turn_started_at,
        }


    @classmethod
    def from_dict(cls, data: dict) -> "VersusGame":
        """
        Restore a VersusGame from its serialized dict form.

        We reconstruct:
        - HumanPlayer for type 'human'
        - AIPlayer for type 'ai'
        - Generic Player otherwise (fallback)
        """
        players_data = data["players"]
        players: List[Player] = []

        for p in players_data:
            p_type = p.get("type", "generic")
            if p_type == "human":
                player = HumanPlayer(player_id=p["id"], name=p["name"])
            elif p_type == "ai":
                intelligence = p.get("intelligence", 50)
                player = AIPlayer(player_id=p["id"], name=p["name"], intelligence=intelligence)
            else:
                player = Player(player_id=p["id"], name=p["name"])
            players.append(player)

        if len(players) != 2:
            raise ValueError("VersusGame.from_dict expects exactly 2 players.")

        ws_data = data["word_states_by_owner"]

        # The constructor expects the word owned by players[0] and players[1].
        word_for_player1 = ws_data[players[0].id]["secret_word"]
        word_for_player2 = ws_data[players[1].id]["secret_word"]

        game = cls(
            player1=players[0],
            player2=players[1],
            word_for_player1=word_for_player1,
            word_for_player2=word_for_player2,
        )

        # Overwrite dynamic state
        game.id = data["id"]
        game.word_states_by_owner = {
            owner_id: WordState.from_dict(ws_dict)
            for owner_id, ws_dict in ws_data.items()
        }
        game.current_player_index = data["current_player_index"]
        game.finished = data["finished"]
        game.winner_id = data["winner_id"]
        game.turn_started_at = data["turn_started_at"]

        return game