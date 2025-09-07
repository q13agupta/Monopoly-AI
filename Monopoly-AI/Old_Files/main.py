import random
from Monopoly.player import Player
from Monopoly.board import tiles
from Monopoly.agent import QLearningAgent

# ---------------- Create Players ----------------
players = [
    Player("Ashiya", tiles),
    Player("Ajay", tiles),
    Player("Arsh", tiles),
    Player("Reema", tiles, human=True)  # Human-controlled
]

# ---------------- Load Agent ----------------
agent = QLearningAgent.load("q_tables.pkl")

# ---------------- Minimal Game Stub ----------------
class GameStub:
    def __init__(self, players, agent):
        self.players = players
        self.board = tiles
        self.agent = agent

game = GameStub(players, agent)
for player in players:
    player.game = game

# ---------------- Game Loop ----------------
for turn in range(1, 26):
    print(f"\n--- Turn {turn} ---")
    for player in players:
        print(f"\n{player.name}'s turn:")

        # Movement & Tile Handling
        player.move()

        # --- Buy property if applicable ---
        if hasattr(player, 'current_property') and player.current_property is not None:
            prop = player.current_property
            state_buy = agent._state_buy(player, prop, game)
            q_actions = agent.q_buy.get(state_buy, None)

            if q_actions:
                action_buy = max(q_actions, key=q_actions.get)
                score = q_actions[action_buy]
                print(f"AGENT SUGGESTION — Buy {prop.name}? -> {'BUY' if action_buy==1 else 'SKIP'} (score={score:.2f})")
            else:
                action_buy = 1 if player.money > prop.price + 100 else 0
                print(f"AGENT SUGGESTION — Buy {prop.name}? -> {'BUY' if action_buy==1 else 'SKIP'} (score=0.00) — No Q-data fallback")

            if action_buy == 1 and player.money >= prop.price:
                player.buy_property(prop)
                print(f"✅ {player.name} bought {prop.name} for £{prop.price}. New balance: £{player.money}")
            else:
                if player.human:
                    print(f"🏷️ Auction started for {prop.name} (£{prop.price})")
                    current_bid = prop.price
                    active_bidders = {p.name: p for p in players}
                    last_bid = current_bid
                    passed_players = set()

                    while len(active_bidders) - len(passed_players) > 1:
                        for p in list(active_bidders.values()):
                            if p.name in passed_players:
                                continue
                            bid = agent.suggest_bid(p, prop, game, last_bid)
                            print(f"{p.name} bids £{bid}" if bid > 0 else f"{p.name} passes")
                            if bid == 0:
                                passed_players.add(p.name)
                            else:
                                last_bid = bid

                    remaining = [p for p in active_bidders.values() if p.name not in passed_players]
                    if remaining:
                        winner = remaining[0]
                        winner.buy_property(prop)
                        print(f"🏆 {winner.name} wins the auction for {prop.name} at £{last_bid}. New balance: £{winner.money}")

            player.current_property = None

        # --- Build houses/hotels ---
        candidate_sets = player.get_candidate_builds()
        build_actions = agent.suggest_build(player, candidate_sets, game)
        for ba in build_actions:
            state_build = agent._state_build(player, ba.get("house_price", 0), game)
            q_build = agent.q_build.get(state_build, None)
            if q_build:
                action_build = max(q_build, key=q_build.get)
                score = q_build[action_build]
                print(f"AGENT SUGGESTION — Build on {ba['colour']}? -> {'BUILD' if action_build==1 else 'SKIP'} (score={score:.2f})")
            else:
                action_build = 1 if ba["action"] == "build" else 0
                print(f"AGENT SUGGESTION — Build on {ba['colour']}? -> {'BUILD' if action_build==1 else 'SKIP'} (score=0.00) — No Q-data fallback")

            if action_build == 1:
                player.build_houses(ba["colour"])
                print(f"🏠 {player.name} built houses on {ba['colour']} set.")



# ---------------- Game Over ----------------
print("\n--- Game Over ---")
for player in players:
    print(f"\n{player.name}: £{player.money}")
    print("Properties owned:")
    for prop in player.properties:
        hotel_str = "Hotel" if prop.hotel else f"{prop.houses} Houses"
        print(f" - {prop.name} ({prop.colour}) | {hotel_str}")
