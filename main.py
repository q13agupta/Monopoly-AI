import random
from Monopoly.player import Player
from Monopoly.board import tiles
from Monopoly.property import Property

# Create players
players = [
    Player("Ashiya", tiles),
    Player("Ajay", tiles),
    Player("Arsh", tiles),
    Player("Reema", tiles)
]

for turn in range(1, 25):
    print(f"\n--- Turn {turn} ---")
    for player in players:
        print(f"\n{player.name}'s turn:")
        player.move()
        
        # Attempt trades
        traded = player.attempt_trade()
        if traded:
            print(f"{player.name} successfully completed a trade this turn!")

        # Build evenly on all completed colour sets
        # Get all unique colours of full sets owned by player
        full_colour_sets = set(
            prop.colour for prop in player.properties
            if player._owns_full_colour_set(prop.colour)
        )

        for colour in full_colour_sets:
            # Properties of this colour owned by player
            colour_props = [p for p in player.properties if p.colour == colour]

            # Decide random target number of houses (1-4) or hotel (5)
            # We'll say 5 means a hotel, since hotels come after 4 houses
            target_build = random.randint(1, 5)
            if target_build <= 4:
             print(f"{player.name} wants to build {target_build} houses on the {colour} colour set.")
            else:
             print(f"{player.name} wants to build a hotel on the {colour} colour set.") 
    

            # Build evenly across properties up to target_build
            # Try to raise each property's houses to target_build (hotel if 5)
            building_happened = True
            while building_happened:
                building_happened = False
                for prop in colour_props:
            
                    current_level = prop.houses
                    # If hotel is built, prop.hotel is True and houses = 4
                    if prop.hotel:
                        continue

                    # If target is 5, build hotel after 4 houses
                    if target_build == 5:
                        if current_level < 4:
                            # Build houses until 4
                            can_build = player.build(prop)
                            if can_build:
                                building_happened = True
                        elif current_level == 4:
                            # Build hotel
                            can_build = player.build(prop)
                            if can_build:
                                building_happened = True
                    else:
                        # target_build between 1-4
                        if current_level < target_build:
                            can_build = player.build(prop)
                            if can_build:
                                building_happened = True

                    # Stop if player runs out of money (build returns False)
                    if not can_build:
                        break

                if not building_happened:
                    # No more builds possible this round on this set
                    break

print("\n--- Game Over ---")
for player in players:
    print(f"\n{player.name}: £{player.money}")
    print(f"Properties owned by {player.name}:")
    for prop in player.properties:
        hotel_str = "Hotel" if prop.hotel else f"{prop.houses} Houses"
        print(f" - {prop.name} ({prop.colour}) | {hotel_str}")
