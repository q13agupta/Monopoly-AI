"""
monopoly_ai.py

Utilities for computing landing probabilities (Markov chain) and a fast
heuristic to recommend house/hotel builds using those probabilities.

This file is written to integrate with your existing project structure:
- It expects the board list you provided in `board.py` (40 tiles)
- It uses your `Property` class methods (calculate_rent, add_house, add_hotel, etc.)

Provided classes / functions:
- dice_distribution(): distribution of two-dice sums (2..12)
- MarkovChain(board, chance_jail_prob=1/6, cc_jail_prob=1/6): builds transition
  matrix and computes stationary distribution (landing probabilities)
- top_build_recommendations(player, landing_probs, max_builds): quick heuristic
  that returns an ordered list of (Property, expected_income_gain, will_be_hotel)
- apply_build_plan(player, plan, min_reserve=150): apply builds while keeping reserve

Notes / simplifications:
- Chance / Community Chest are modelled using the simplified card set in your
  draw_card(): ~1/6 chance to send to jail, otherwise they do not move the player.
- Jail behaviour is simplified: being in jail has a 1/6 chance to release each turn
  (rolling doubles) and 5/6 to stay. This underestimates the real chance of leaving
  by paying after 3 turns but is fast and useful for heuristics.
- The Markov chain assumes standard movement (sum of two dice) and handles the
  "Go To Jail" square by forcing moves to jail.

Next steps I can implement (if you want):
- Replace simplifications with a fuller jail-state model (tracks jail turn counts)
- Wrap the game into a Gym-like RL environment (state vector, step(), reset())
- Add a baseline RL agent (tabular / DQN) for the building decision

"""
from typing import List, Tuple, Dict
import numpy as np
import random
from collections import defaultdict
from Monopoly.board import tiles

# --- Dice distribution ---

def dice_distribution():
    """Return probability distribution for two 6-sided dice sums (2..12).
    Returns a dict sum -> probability."""
    dist = defaultdict(int)
    for d1 in range(1, 7):
        for d2 in range(1, 7):
            dist[d1 + d2] += 1
    total = 36
    return {s: cnt / total for s, cnt in dist.items()}


# --- Markov chain for landing probabilities ---
class MarkovChain:
    def __init__(self, board: List, chance_jail_prob: float = 1/6, cc_jail_prob: float = 1/6):
        self.board = board
        self.N = len(board)
        self.chance_jail_prob = chance_jail_prob
        self.cc_jail_prob = cc_jail_prob
        self.go_to_jail_idx = self.board.index("Go To Jail") if "Go To Jail" in self.board else None
        # Jail index (tile "Jail")
        self.jail_idx = None
        for i, t in enumerate(self.board):
            if t == "Jail":
                self.jail_idx = i
                break
        self.dice_dist = dice_distribution()
        self.P = self._build_transition_matrix()

    def _is_chance(self, idx):
        return self.board[idx] == "Chance"

    def _is_community(self, idx):
        return self.board[idx] == "Community Chest"

    def _build_transition_matrix(self):
        N = self.N
        P = np.zeros((N, N))

        for i in range(N):
            # If "Go To Jail" landing, move to jail deterministically
            if i == self.go_to_jail_idx:
                if self.jail_idx is not None:
                    P[i, self.jail_idx] = 1.0
                else:
                    P[i, i] = 1.0
                continue

            # For each dice outcome, compute landing square and apply Chance/CC effects
            for roll_sum, prob in self.dice_dist.items():
                j = (i + roll_sum) % N

                # If this landing square is Go To Jail, move to jail
                if j == self.go_to_jail_idx and self.jail_idx is not None:
                    P[i, self.jail_idx] += prob
                    continue

                # Chance and Community Chest are simplified: ~chance_jail_prob to go to jail
                if self._is_chance(j):
                    if self.jail_idx is not None:
                        P[i, self.jail_idx] += prob * self.chance_jail_prob
                    P[i, j] += prob * (1 - self.chance_jail_prob)
                    continue

                if self._is_community(j):
                    if self.jail_idx is not None:
                        P[i, self.jail_idx] += prob * self.cc_jail_prob
                    P[i, j] += prob * (1 - self.cc_jail_prob)
                    continue

                # Normal landing
                P[i, j] += prob

        # Simplified jail handling: when on jail tile, assume 1/6 chance to leave (roll doubles)
        # and (5/6) to remain. When leaving, distribute according to dice distribution.
        if self.jail_idx is not None:
            jidx = self.jail_idx
            P[jidx, :] = 0.0
            leave_prob = 1 / 6.0
            stay_prob = 1 - leave_prob
            P[jidx, jidx] = stay_prob
            for roll_sum, prob in self.dice_dist.items():
                dest = (jidx + roll_sum) % N
                # applying same Chance/CC/go-to-jail logic as above for dest
                if dest == self.go_to_jail_idx and self.jail_idx is not None:
                    P[jidx, self.jail_idx] += leave_prob * prob
                elif self._is_chance(dest):
                    if self.jail_idx is not None:
                        P[jidx, self.jail_idx] += leave_prob * prob * self.chance_jail_prob
                    P[jidx, dest] += leave_prob * prob * (1 - self.chance_jail_prob)
                elif self._is_community(dest):
                    if self.jail_idx is not None:
                        P[jidx, self.jail_idx] += leave_prob * prob * self.cc_jail_prob
                    P[jidx, dest] += leave_prob * prob * (1 - self.cc_jail_prob)
                else:
                    P[jidx, dest] += leave_prob * prob

        # Sanity: rows should sum to 1
        row_sums = P.sum(axis=1)
        for r in range(N):
            if row_sums[r] == 0:
                P[r, r] = 1.0
            else:
                P[r, :] /= row_sums[r]

        return P

    def stationary_distribution(self, tol=1e-12, max_iter=10000):
        """Compute stationary distribution via power iteration on P^T.
        Returns a vector length N summing to 1."""
        N = self.N
        pi = np.ones(N) / N
        PT = self.P.T
        for _ in range(max_iter):
            new_pi = PT.dot(pi)
            if np.linalg.norm(new_pi - pi, ord=1) < tol:
                return new_pi
            pi = new_pi
        return pi


# --- Building recommendation helpers ---

def expected_rent_increase(prop, landing_prob, owner=None):
    """Compute expected rent increase for adding one house (or hotel conversion)
    using the property's rent table and a landing probability.

    Returns (delta_expected_income, will_be_hotel_boolean)
    """
    # current rent
    owns_full = False
    if owner:
        owns_full = owner._owns_full_colour_set(prop.colour)
    current_rent = prop.calculate_rent(owns_full_colour_set=owns_full, roll_dice=7) if prop.colour == "Utility" else prop.calculate_rent(owns_full_colour_set=owns_full)

    # determine post-build rent
    if prop.hotel:
        return 0.0, False
    if prop.houses < 4:
        # rent after adding one house
        # temporarily simulate
        orig_houses = prop.houses
        prop.houses += 1
        new_rent = prop.calculate_rent(owns_full_colour_set=owns_full)
        prop.houses = orig_houses
        return (landing_prob * (new_rent - current_rent)), False
    elif prop.houses == 4 and prop.can_build_hotel():
        # hotel conversion
        orig_houses = prop.houses
        prop.houses = 0
        prop.hotel = True
        new_rent = prop.calculate_rent(owns_full_colour_set=owns_full)
        prop.houses = orig_houses
        prop.hotel = False
        return (landing_prob * (new_rent - current_rent)), True
    return 0.0, False


def top_build_recommendations(player, landing_probs: np.ndarray, max_builds: int = 10, min_reserve: int = 150):
    """Return a prioritized list of builds for `max_builds` houses/hotels.

    Each item: (Property, expected_income_gain, is_hotel_conversion, house_cost)
    The routine respects even-building by selecting lowest-house properties in each
    full-colour set first.
    """
    # Gather player's full, buildable colour sets
    colour_sets = defaultdict(list)
    for p in player.properties:
        if p.buildable and not p.mortgaged and player._owns_full_colour_set(p.colour):
            colour_sets[p.colour].append(p)

    if not colour_sets:
        return []

    candidate_actions = []
    for colour, props in colour_sets.items():
        # even-build rule: always consider properties with the fewest houses first
        props_sorted = sorted(props, key=lambda x: (x.houses if not x.hotel else float('inf')))
        for prop in props_sorted:
            idx = player.board.index(prop)
            prob = float(landing_probs[idx])
            delta_income, will_hotel = expected_rent_increase(prop, prob, owner=player)
            candidate_actions.append((prop, delta_income, will_hotel, prop.house_price))

    # sort by expected income per £ cost (ROI-like)
    candidate_actions = [c for c in candidate_actions if c[1] > 0]
    candidate_actions.sort(key=lambda x: (x[1] / (x[3] if x[3] > 0 else 1)), reverse=True)

    # Trim to max_builds and affordability given min_reserve
    plan = []
    money_available = player.money - min_reserve
    for prop, income, is_hotel, cost in candidate_actions:
        if len(plan) >= max_builds:
            break
        if money_available < cost:
            continue
        # Also check even-build constraint: don't build if it would make houses uneven by >1
        set_props = [p for p in player.properties if p.colour == prop.colour]
        min_houses = min((p.houses if not p.hotel else 5) for p in set_props)
        if (prop.houses if not prop.hotel else 5) > min_houses + 1:
            continue
        plan.append((prop, income, is_hotel, cost))
        money_available -= cost

    return plan


def apply_build_plan(player, plan: List[Tuple], min_reserve: int = 150):
    """Apply a plan produced by top_build_recommendations.
    Returns number of builds performed and total cost.
    """
    built = 0
    total_cost = 0
    for prop, income, is_hotel, cost in plan:
        if player.money - cost < min_reserve:
            break
        if is_hotel and prop.can_build_hotel():
            if prop.add_hotel():
                player.money -= cost
                built += 1
                total_cost += cost
        elif prop.add_house():
            player.money -= cost
            built += 1
            total_cost += cost

    return built, total_cost

