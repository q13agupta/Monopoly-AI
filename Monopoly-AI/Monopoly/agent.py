# Monopoly/agent.py
import random
import math
import pickle
from collections import defaultdict, Counter
from typing import List, Dict, Any, Optional, Tuple

# Simple type hints
Suggestion = Dict[str, Any]

class Agent:
    """Base interface for advisors."""
    def suggest_buy(self, player, property_tile, game) -> Suggestion:
        raise NotImplementedError

    def suggest_trade(self, player, other_players, game) -> List[Suggestion]:
        raise NotImplementedError

    def suggest_jail_action(self, player, game) -> Suggestion:
        raise NotImplementedError

    def suggest_build(self, player, candidate_props: List, game) -> List[Suggestion]:
        raise NotImplementedError

# -----------------------
# Markov / Monte-Carlo helpers (fast estimators)
# -----------------------
class MarkovEstimator:
    """
    Estimate landing probabilities by simulating many dice-only turns.
    This is a lightweight empirical estimator (ignores full card logic
    for speed but includes Go-To-Jail).
    """
    def __init__(self, board, n_sim=2000):
        self.board = board
        self.n_sim = n_sim
        self.probs = None

    def estimate(self, start_pos=0):
        counts = Counter()
        pos = start_pos
        n = self.n_sim
        for _ in range(n):
            d1 = random.randint(1, 6)
            d2 = random.randint(1, 6)
            steps = d1 + d2
            pos = (pos + steps) % len(self.board)
            tile = self.board[pos]
            # simple card effect: if Go To Jail tile, jump to jail
            if tile == "Go To Jail":
                pos = 10
            counts[pos] += 1
        total = sum(counts.values())
        self.probs = {i: counts[i] / total for i in range(len(self.board))}
        return self.probs

class MonteCarloEvaluator:
    """
    Perform short Monte Carlo rollouts to estimate delta win-rate or
    expected cash change when testing a candidate action.
    This is intentionally lightweight and uses the provided `game_runner`
    function (user must pass a callable that can clone + run short rollouts).
    """
    def __init__(self, game_runner):
        self.game_runner = game_runner

    def evaluate_action(self, clone_state_fn, apply_action_fn, n_rollouts=200, rollout_depth=30):
        """
        clone_state_fn(): returns a deep copy of the current game state
        apply_action_fn(state): applies the candidate action to `state` before rollouts
        Returns: dict with 'win_rate_delta' and 'avg_cash_delta' (both relative)
        """
        wins = 0
        cash_results = []
        for _ in range(n_rollouts):
            st = clone_state_fn()
            apply_action_fn(st)
            winner, final_money = self.game_runner(st, max_turns=rollout_depth)
            # winner is the Player instance who won in the rollout (or None)
            wins += (1 if winner == st.current_player else 0)
            cash_results.append(final_money.get(st.current_player.name, st.current_player.money))
        return {
            "win_rate": wins / n_rollouts,
            "avg_cash": sum(cash_results) / len(cash_results) if cash_results else 0
        }

# -----------------------
# Rule-based agent (fast)
# -----------------------
class RuleBasedAgent(Agent):
    def __init__(self, reserve=150):
        self.reserve = reserve

    def suggest_bid(self, player, property_tile, game):
        # Score higher if completes a color set
        score_multiplier = 1.5 if player._owns_full_colour_set(property_tile.colour) else 1.0
        base_bid = int(property_tile.price * score_multiplier)
        # Don't exceed player money
        return min(base_bid, player.money)

    def _completes_set_if_bought(self, player, prop, game):
        colour = prop.colour
        if colour in ("Station", "Utility"):
            return False
        all_of_colour = [t for t in game.board if hasattr(t, "colour") and t.colour == colour]
        owned = sum(1 for p in player.properties if p.colour == colour)
        return owned == len(all_of_colour) - 1

    def suggest_buy(self, player, property_tile, game):
        # Always recommend buy if buying completes a set
        if self._completes_set_if_bought(player, property_tile, game):
            return {"action": "buy", "score": 1.0, "reason": "Buying completes a monopoly — strong move."}
        # Cheap properties are good early buys if cash remains above reserve
        if property_tile.price <= 100 and player.money - property_tile.price >= self.reserve:
            return {"action": "buy", "score": 0.7, "reason": "Cheap property; good for set-building."}
        # Utilities: buy if cheap and you have at least one utility already
        if property_tile.colour == "Utility" and player.money - property_tile.price >= self.reserve:
            return {"action": "buy", "score": 0.5, "reason": "Utility provides steady income when you own both."}
        return {"action": "skip", "score": 0.0, "reason": "Price too high or would reduce reserve."}

    def suggest_trade(self, player, other_players, game):
        proposals = []
        # Propose cash offers if a trade would complete a set
        all_props = [t for t in game.board if isinstance(t, type(player.properties[0]))] if player.properties else [t for t in game.board if hasattr(t, "price")]
        for opp in other_players:
            if opp == player: 
                continue
            for prop in list(opp.properties):
                # if acquiring prop would give a monopoly
                if self._completes_set_if_bought(player, prop, game):
                    offer = int(prop.price * 1.5)
                    if player.money >= max(offer - 200, 0):  # small heuristic allowance
                        proposals.append({
                            "offer": {"cash": offer, "properties": []},
                            "target": prop,
                            "expected_value_gain": offer * 0.1,
                            "confidence": 0.6,
                            "reason": f"Completes {prop.colour} set — propose £{offer}."
                        })
        return proposals

    def suggest_jail_action(self, player, game):
        monopolies = sum(1 for c in set(p.colour for p in player.properties) if player._owns_full_colour_set(c))
        # Late-game (has monopolies): prefer to stay in jail to avoid landing on opponents
        if monopolies >= 2:
            return {"action": "stay_try_roll", "score": 0.6, "reason": "Has multiple monopolies — safer to avoid moving."}
        # If low money, try rolls (can't pay)
        if player.money < 60:
            return {"action": "try_roll", "score": 0.4, "reason": "Preserve money; attempt to roll doubles."}
        # Default: pay to get moving early
        return {"action": "pay", "score": 0.5, "reason": "Early game mobility preferred; pay £50 to get out."}
    def suggest_bid(self, player, property_tile, game):
        # Score higher if completes a color set
        score_multiplier = 1.5 if player._owns_full_colour_set(property_tile.colour) else 1.0
        base_bid = int(property_tile.price * score_multiplier)
        # Don't exceed player money
        return min(base_bid, player.money)

    def suggest_build(self, player, candidate_props: List, game):
        # Candidate props is a list of properties in completed sets
        # Heuristic: build on set with highest house_price * expected landings
        estimator = MarkovEstimator(game.board, n_sim=1500)
        probs = estimator.estimate()
        best = []
        for colour, props in candidate_props.items():
            # expected landing probability for any property in this set ~ sum(probs of those indices)
            idxs = [game.board.index(p) for p in props]
            p_land = sum(probs[i] for i in idxs)
            # rent delta per house roughly rent_levels[1] - rent_levels[0] (if defined)
            sample = props[0]
            if sample.rent_levels:
                delta = sample.rent_levels[1] - sample.rent_levels[0]
            else:
                delta = sample.base_rent
            ev_per_house = p_land * delta
            roi = ev_per_house / sample.house_price if sample.house_price else 0
            best.append({
                "colour": colour,
                "ev_per_house": ev_per_house,
                "roi": roi,
                "reason": f"Est. p_land={p_land:.3f}, EV/house≈£{ev_per_house:.2f}, cost={sample.house_price}"
            })
        best_sorted = sorted(best, key=lambda x: x["roi"], reverse=True)
        return best_sorted

# -----------------------
# Q-Learning agent (tabular) - focused on discrete decision modules
# -----------------------
# Monopoly/agent.py

import random
import pickle
from collections import defaultdict
from typing import Dict, List

class QLearningAgent:
    """
    Tabular Q-learning agent for Monopoly:
      - Buy/skip at property
      - Jail action: try_roll / pay / use_card
      - Build: build_cheapest / skip
    State is coarse for tractable Q-tables.
    Save/Load via pickle.
    """
    def __init__(self, epsilon=0.1, alpha=0.1, gamma=0.99):
        self.q_buy = defaultdict(lambda: {0: 0.0, 1: 0.0})       # 0: skip, 1: buy
        self.q_jail = defaultdict(lambda: {0: 0.0, 1: 0.0, 2: 0.0}) # 0: try_roll,1:pay,2:use_card
        self.q_build = defaultdict(lambda: {0: 0.0, 1: 0.0})      # 0: skip, 1: build_cheapest
        self.epsilon = epsilon
        self.alpha = alpha
        self.gamma = gamma

    # --- State helpers ---
    def _cash_bucket(self, cash):
        if cash < 100: return 0
        if cash < 300: return 1
        if cash < 700: return 2
        return 3

    def _monopoly_count(self, player):
        return sum(1 for c in set(p.colour for p in player.properties) if player._owns_full_colour_set(c))

    def _pos_zone(self, player, board_len):
        return player.position * 10 // board_len

    def _state_buy(self, player, prop, game):
        return (self._cash_bucket(player.money), self._monopoly_count(player),
                self._pos_zone(player, len(game.board)), prop.colour)

    def _state_jail(self, player, game):
        return (self._cash_bucket(player.money), self._monopoly_count(player),
                self._pos_zone(player, len(game.board)))

    def _state_build(self, player, cheapest_house_price, game):
        return (self._cash_bucket(player.money), self._monopoly_count(player), cheapest_house_price)

    def _state_trade(self, player, game):
        full_sets = sum(1 for colour in ["Brown","Light Blue","Pink","Orange","Red","Yellow","Green","Dark Blue"]
                        if player._owns_full_colour_set(colour))
        return (player.money, len(player.properties), full_sets)

    # --- Action selection ---
    def suggest_buy(self, player, property_tile, game):
        s = self._state_buy(player, property_tile, game)
        if random.random() < self.epsilon:
            a = random.choice([0,1])
        else:
            q = self.q_buy[s]
            a = max(q, key=q.get)
        reason = "QL policy" if any(self.q_buy[s].values()) else "No Q-data fallback"
        return {"action": "buy" if a==1 else "skip", "score": float(self.q_buy[s][a]), "reason": reason}

    def suggest_jail_action(self, player, game):
        s = self._state_jail(player, game)
        if random.random() < self.epsilon:
            a = random.choice([0,1,2])
        else:
            q = self.q_jail[s]
            a = max(q, key=q.get)
        mapping = {0: "try_roll", 1: "pay", 2: "use_card"}
        reason = "QL policy" if any(self.q_jail[s].values()) else "No Q-data"
        return {"action": mapping[a], "score": float(self.q_jail[s][a]), "reason": reason}

    def suggest_trade(self, player, other_players, game):
        from Monopoly.agent import RuleBasedAgent
        return RuleBasedAgent().suggest_trade(player, other_players, game)

    def suggest_build(self, player, candidate_props: Dict[str, List], game):
        if not candidate_props:
            return []
        cheapest_price = min([props[0].house_price for props in candidate_props.values()])
        s = self._state_build(player, cheapest_price, game)
        if random.random() < self.epsilon:
            a = random.choice([0,1])
        else:
            q = self.q_build[s]
            a = max(q, key=q.get)
        reason = "QL policy" if any(self.q_build[s].values()) else "No Q-data"
        if a == 0:
            return [{"action": "skip", "score": self.q_build[s][0], "reason": reason}]
        else:
            best_colour = min(candidate_props.keys(), key=lambda k: candidate_props[k][0].house_price)
            return [{"action": "build", "colour": best_colour,
                     "house_price": candidate_props[best_colour][0].house_price,
                     "score": self.q_build[s][1], "reason": reason}]

    # --- Auction / Bid suggestion ---
    def suggest_bid(self, player, property_tile, game, current_bid):
        base_price = property_tile.price
        cash = player.money
        bid_increment = max(10, int(base_price * 0.05))
        completes_set = all(p.owner == player for p in game.board
                            if hasattr(p, 'colour') and p.colour == property_tile.colour)
        max_affordable = cash - 100
        value_factor = base_price * (1.5 if completes_set else 1.0)
        suggested_bid = min(max(current_bid + bid_increment, int(value_factor)), max_affordable)
        if suggested_bid <= current_bid or suggested_bid > max_affordable:
            return 0  # pass
        return suggested_bid

    # --- Training updates ---
    def update_episode(self, episode_records, G=None):
        for record in episode_records:
            if len(record) == 4:
                module, s, a, reward = record
            else:
                module, s, a = record
                reward = 0

            if module == "buy":
                qdict = self.q_buy[s]
            elif module == "jail":
                qdict = self.q_jail[s]
            elif module == "build":
                qdict = self.q_build[s]
            else:
                continue

            update_value = reward if reward is not None else (G if G is not None else 0)
            qdict[a] += self.alpha * (update_value - qdict[a])

    # --- Save / Load ---
    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump({
                "q_buy": dict(self.q_buy),
                "q_jail": dict(self.q_jail),
                "q_build": dict(self.q_build),
                "epsilon": self.epsilon,
                "alpha": self.alpha,
                "gamma": self.gamma
            }, f)

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj = cls(epsilon=data.get("epsilon", 0.05), alpha=data.get("alpha", 0.1), gamma=data.get("gamma", 0.99))
        obj.q_buy = defaultdict(lambda: {0:0.0,1:0.0}, data.get("q_buy", {}))
        obj.q_jail = defaultdict(lambda: {0:0.0,1:0.0,2:0.0}, data.get("q_jail", {}))
        obj.q_build = defaultdict(lambda: {0:0.0,1:0.0}, data.get("q_build", {}))
        return obj
