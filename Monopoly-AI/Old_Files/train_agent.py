# Monopoly/train_agent.py

import random
from Monopoly.player import Player
from Monopoly.board import tiles
from Monopoly.agent import QLearningAgent
from Monopoly.property import Property  # Ensure same Property class is imported

NUM_EPISODES = 2000  # Increase for better learning
MAX_TURNS = 50       # Max turns per game

def train_q_agent_realistic():
    agent = QLearningAgent(epsilon=0.2)  # exploration

    for episode in range(1, NUM_EPISODES + 1):
        # Initialize AI players only
        players = [
            Player("Ashiya", tiles),
            Player("Ajay", tiles),
            Player("Arsh", tiles)
        ]

        # Minimal game stub
        class GameStub:
            def __init__(self, players):
                self.players = players
                self.board = tiles

        game = GameStub(players)
        for player in players:
            player.game = game

        # Track episode records per player
        player_records = {p.name: [] for p in players}

        for turn in range(1, MAX_TURNS + 1):
            for player in players:
                # --- Move ---
                player.move()

                # --- Buy property if applicable ---
                if hasattr(player, 'current_property') and isinstance(player.current_property, Property):
                    prop = player.current_property

                    # Record previous state
                    prev_net_worth = player.money + sum(
                        p.price for p in player.properties if isinstance(p, Property)
                    )
                    prev_expected_rent = sum(
                        p.expected_rent(p_land=0.05) for p in player.properties if isinstance(p, Property)
                    )

                    # AI decision
                    state_buy = agent._state_buy(player, prop, game)
                    action_buy = agent.select_action(player, "buy", state_buy)

                    if action_buy == 1 and player.money >= prop.price:
                        player.buy_property(prop)
                    # else: skip (auction handled elsewhere)

                    # Calculate reward
                    new_net_worth = player.money + sum(
                        p.price for p in player.properties if isinstance(p, Property)
                    )
                    new_expected_rent = sum(
                        p.expected_rent(p_land=0.05) for p in player.properties if isinstance(p, Property)
                    )
                    reward = (new_net_worth - prev_net_worth) + (new_expected_rent - prev_expected_rent)
                    player_records[player.name].append(("buy", state_buy, action_buy, reward))

                    player.current_property = None

                # --- Build houses/hotels ---
                candidate_sets = player.get_candidate_builds()
                build_actions = agent.suggest_build(player, candidate_sets, game)

                for ba in build_actions:
                    prev_net_worth = player.money + sum(
                        p.price for p in player.properties if isinstance(p, Property)
                    )
                    prev_expected_rent = sum(
                       p.expected_rent(p_land=0.05, owns_full_colour_set=player.owns_full_set(p.colour)) 
                       for p in player.properties 
                       if isinstance(p, Property) and hasattr(p, 'expected_rent')
                     )

                    if ba["action"] == "build":
                        player.build_houses(ba["colour"])
                        action_build = 1
                    else:
                        action_build = 0

                    state_build = agent._state_build(player, ba.get("house_price", 0), game)

                    # Reward = delta net worth + delta expected rent
                    new_net_worth = player.money + sum(
                        p.price for p in player.properties if isinstance(p, Property)
                    )
                    new_expected_rent = sum(
                      p.expected_rent(p_land=0.05, owns_full_colour_set=player.owns_full_set(p.colour)) 
                      for p in player.properties 
                      if isinstance(p, Property) and hasattr(p, 'expected_rent')
                    )

                    reward_build = (new_net_worth - prev_net_worth) + (new_expected_rent - prev_expected_rent)

                    player_records[player.name].append(("build", state_build, action_build, reward_build))

                # --- Trading logic ---
                traded = player.attempt_trade()
                if traded:
                    prev_net_worth = player.money + sum(
                        p.price for p in player.properties if isinstance(p, Property)
                    )
                    prev_expected_rent = sum(
                      p.expected_rent(p_land=0.05, owns_full_colour_set=player.owns_full_set(p.colour)) 
                      for p in player.properties 
                      if isinstance(p, Property) and hasattr(p, 'expected_rent')
                    )
                    

                    new_net_worth = player.money + sum(
                        p.price for p in player.properties if isinstance(p, Property)
                    )
                    new_expected_rent =sum(
                          p.expected_rent(p_land=0.05, owns_full_colour_set=player.owns_full_set(p.colour)) 
                          for p in player.properties 
                          if isinstance(p, Property) and hasattr(p, 'expected_rent')
                        )
                    reward_trade = (new_net_worth - prev_net_worth) + (new_expected_rent - prev_expected_rent)

                    state_trade = agent._state_trade(player, game)
                    player_records[player.name].append(("trade", state_trade, 1, reward_trade))

        # --- End of episode: update Q-tables ---
        for p in players:
            final_net_worth = p.money + sum(
                prop.price for prop in p.properties if isinstance(prop, Property)
            )
            final_expected_rent = sum(
              p.expected_rent(p_land=0.05, owns_full_colour_set=player.owns_full_set(p.colour)) 
              for p in player.properties 
              if isinstance(p, Property) and hasattr(p, 'expected_rent')
             )

            final_reward = final_net_worth + final_expected_rent
            agent.update_episode(player_records[p.name], final_reward)

        if episode % 100 == 0:
            print(f"Episode {episode}/{NUM_EPISODES} completed.")

    # Save Q-tables
    agent.save("q_tables.pkl")
    print("Training complete. Q-tables saved to q_tables.pkl.")

# Run training
train_q_agent_realistic()
