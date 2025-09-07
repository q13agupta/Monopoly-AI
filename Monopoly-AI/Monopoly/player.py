import random
from Monopoly.property import Property
from itertools import combinations 
from collections import defaultdict 

class Player:
    def __init__(self, name="Player", board=None, human=False):
        self.name = name
        self.position = 0
        self.money = 1500
        self.in_jail = False
        self.jail_turns = 0
        self.doubles_count = 0
        self.board = board if board else []
        self.properties = []
        self._announced_sets = set()
        self.game = None
        self.human = human  # New flag for human-controlled player


    def roll_dice(self):
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        self.last_roll_total = die1 + die2
        print(f"{self.name} rolls: {die1} + {die2} = {die1 + die2}")
        return die1, die2

    def go_to_jail(self):
        print(f"{self.name} is sent to jail!")
        self.position = 10  # Jail tile index
        self.in_jail = True
        self.jail_turns = 0
        self.doubles_count = 0
    def handle_jail(self):
        if not self.in_jail:
            return
        agent = getattr(self.game, "agent", None)
        suggestion = None
        if agent:
            suggestion = agent.suggest_jail_action(self, self.game)
            advice_text = self.score_to_advice(suggestion['score'])
            print(f"AGENT SUGGESTION — Jail action: {suggestion['action']} ({advice_text}) — {suggestion['reason']}")

        if self.human:
            choice = input("Type 'pay' to pay £50, 'roll' to attempt doubles, or 'stay': ").strip().lower()
            if choice == 'pay':
                self.money -= 50
                self.in_jail = False
                print(f"{self.name} pays £50 to get out of jail.")
            elif choice == 'roll':
                die1, die2 = self.roll_dice()
                if die1 == die2:
                    self.in_jail = False
                    print(f"{self.name} rolled doubles and is released!")
                else:
                    print(f"{self.name} stays in jail.")
            else:
                print(f"{self.name} stays in jail.")
        else:
            # AI-controlled: 70% chance to follow suggestion
            follow_ai = random.random() < 0.7
            if follow_ai and suggestion and suggestion['action'] == 'pay':
                self.money -= 50
                self.in_jail = False
                print(f"{self.name} pays £50 to get out of jail (AI choice).")
            else:
                print(f"{self.name} stays in jail.")

    def _owns_full_colour_set(self, colour):
        """Check if player owns all properties of a given colour"""
        colour_props = [tile for tile in self.board if isinstance(tile, Property) and getattr(tile, "colour", None) == colour]
        return all(getattr(p, "owner", None) == self for p in colour_props)


    def buy_property(self, property_tile):
        """Attempt to buy a property, respecting agent advice and human input"""
        agent = getattr(self.game, "agent", None)
        buy_action = True

        # Agent suggestion
        if agent:
            suggestion = agent.suggest_buy(self, property_tile, self.game)
            print(f"AGENT SUGGESTION — Buy {property_tile.name}? -> {suggestion['action'].upper()} "
                  f"(score={suggestion.get('score',0):.2f}) — {suggestion.get('reason')}")
            if not self.human and suggestion['action'] == "skip":
                buy_action = False

        # Human input
        if self.human:
            choice = input(f"{self.name}, do you want to buy {property_tile.name} for £{property_tile.price}? (y/n, Enter=agent suggestion): ").strip().lower()
            if choice == "y":
                buy_action = True
            elif choice == "n":
                buy_action = False
            else:
                buy_action = suggestion['action'] == "buy"

        if buy_action and self.money >= property_tile.price:
            print(f"{self.name} buys {property_tile.name} for £{property_tile.price}")
            self.money -= property_tile.price
            property_tile.owner = self
            self.properties.append(property_tile)
            print(f"New balance: £{self.money}")
            if self._owns_full_colour_set(property_tile.colour) and property_tile.colour not in self._announced_sets:
                print(f"✨ {self.name} now owns all {property_tile.colour} properties!")
                self._announced_sets.add(property_tile.colour)
            self.ensure_non_negative_balance()
            return True
        elif not buy_action:
            print(f"{self.name} chooses NOT to buy {property_tile.name}")
            self.auction_property(property_tile)
            return False
        else:
            print(f"{self.name} cannot afford {property_tile.name}")
            return False
    def decide_buy_property(self, prop, agent):
        """
        AI decides whether to buy a property.
        Returns True if bought, False if skipped, None if human.
        """
        if self.human:
            return None

        state = agent._state_buy(self, prop, self.game)
        action = agent.select_action(self, "buy", state)  # 1=buy, 0=skip
        q_val = agent.q_buy.get(state, {}).get(action, None)

        print(f"{self.name} evaluating {prop.name}: Q-value={q_val}, action={'Buy' if action==1 else 'Skip'}")

        if action == 1 and self.money >= prop.price:
            self.buy_property(prop)
            return True
        return False

    def auction_property(self, property_tile):
        print(f"🏷️ Auction started for {property_tile.name} (£{property_tile.price})")
        active_bidders = [p for p in self.game.players if p.money > 0]
        highest_bid = property_tile.price - 1
        highest_bidder = None
        passed_players = set()

        def ai_bid(player, current_highest):
            # Simple AI: bid up to 1.2x property price if cash allows, scaled to player money
            max_afford = player.money
            base = property_tile.price
            bid = min(base + random.randint(5, 20), int(1.2 * base), max_afford)
            return max(bid, current_highest + 1) if bid > current_highest else 0

        while len(active_bidders) > 0:
            bid_in_round = False
            for player in active_bidders[:]:
                if player in passed_players:
                    continue

                min_bid = highest_bid + 1
                if player.human:
                    suggestion = ai_bid(player, highest_bid)
                    try:
                        bid_input = input(f"{player.name}, enter your bid (current: £{highest_bid}, AI suggests £{suggestion}, 0=pass): ")
                        bid = int(bid_input) if bid_input else suggestion
                    except ValueError:
                        bid = suggestion
                else:
                    bid = ai_bid(player, highest_bid)
                    if bid == 0:
                        passed_players.add(player)
                        print(f"{player.name} passes")
                        continue
                    print(f"{player.name} bids £{bid}")

                if bid <= highest_bid or bid > player.money:
                    passed_players.add(player)
                    if player.human:
                        print(f"{player.name} passes")
                    continue

                # Valid bid
                highest_bid = bid
                highest_bidder = player
                bid_in_round = True

            if not bid_in_round:
                break

            # remove passed players
            active_bidders = [p for p in active_bidders if p not in passed_players]

        if highest_bidder:
            highest_bidder.money -= highest_bid
            property_tile.owner = highest_bidder
            highest_bidder.properties.append(property_tile)
            print(f"🏆 {highest_bidder.name} wins the auction for {property_tile.name} at £{highest_bid}. New balance: £{highest_bidder.money}")
        else:
            print(f"No bids placed for {property_tile.name}")
    
    def mortgage_property(self, property_to_mortgage):
        if property_to_mortgage.owner != self:
            return False
        if property_to_mortgage.mortgaged:
            print(f"{property_to_mortgage.name} is already mortgaged.")
            return False
        if property_to_mortgage.houses > 0 or property_to_mortgage.hotel:
            print(f"Cannot mortgage {property_to_mortgage.name} with houses or hotels built.")
            return False
        
        success = property_to_mortgage.mortgage()
        if success:
            self.money += property_to_mortgage.mortgage_value
            print(f"{self.name} received £{property_to_mortgage.mortgage_value} from mortgaging {property_to_mortgage.name}. Current money: £{self.money}")
            return True
        return False
    

    def handle_buy_property(self, property_tile):
        if property_tile.owner or not getattr(self.game, "agent", None):
            return
        agent = self.game.agent
        suggestion = agent.suggest_buy(self, property_tile, self.game)
        advice_text = self.score_to_advice(suggestion['score'])
        print(f"AGENT SUGGESTION — Buy {property_tile.name}? {advice_text} | Reason: {suggestion['reason']}")
        
        if self.human:
            choice = input("Type 'yes' to buy, 'no' to skip: ").strip().lower()
            if choice == 'yes':
                self.buy_property(property_tile)
        else:
            follow_ai = random.random() < 0.2
            if follow_ai and suggestion['score'] > 0.5:
                self.buy_property(property_tile)

    def handle_build_houses(self):
        candidate_props = {}
        for prop in self.properties:
            if getattr(prop, "buildable", False) and not getattr(prop, "mortgaged", False) and self._owns_full_colour_set(getattr(prop, "colour", None)):
                candidate_props.setdefault(prop.colour, []).append(prop)
        
        agent = getattr(self.game, "agent", None)
        if candidate_props and agent:
            build_suggestions = agent.suggest_build(self, candidate_props, self.game)
            if self.human:
                print("\nAGENT BUILD SUGGESTIONS:")
                for s in build_suggestions[:3]:
                    advice_text = self.score_to_advice(s.get('score', 0))
                    print(f"  - {s.get('colour','?')}: {advice_text} | Reason: {s.get('reason')}")
                choice = input("Type colour to build on or 'skip': ").strip()
                if choice in candidate_props:
                    print(f"Building on {choice}...")
                    self.build_houses()
            else:
                follow_ai = random.random() < 0.7
                if follow_ai:
                    self.build_houses()

    def score_to_advice(self, score):
        """Translate AI numeric score into user-friendly advice"""
        if score > 0.75:
            return "Strongly recommended"
        elif score > 0.5:
            return "Recommended"
        elif score > 0.25:
            return "Optional"
        else:
            return "Not recommended"


    def unmortgage_property(self, property_to_unmortgage):
        if property_to_unmortgage.owner != self:
            return False
        if not property_to_unmortgage.mortgaged:
            return False
        
        cost = property_to_unmortgage.unmortgage_cost()
        if self.money < cost:
            print(f"{self.name} cannot afford to unmortgage {property_to_unmortgage.name}. Needs £{cost:.2f}, has £{self.money}.")
            return False
        self.money -= cost
        print(f"{self.name} paid £{cost:.2f} to unmortgage {property_to_unmortgage.name}. Remaining money: £{self.money}")
        if not self.ensure_non_negative_balance():  # Added after unmortgage
            return False
        return True


    def attempt_trade(self):
        all_properties = [tile for tile in self.board if isinstance(tile, Property)]
        agent = getattr(self.game, "agent", None)
        if agent is not None:
           trade_suggestions = agent.suggest_trade(self, [p for p in self.game.players if p != self], self.game)
           if trade_suggestions:
            print("AGENT TRADE SUGGESTIONS:")
            for s in trade_suggestions[:3]:
              tgt = getattr(s.get("target"), "name", None)
              print(f"  - For {tgt}: offer {s['offer']} | EV≈{s.get('expected_value_gain'):.2f} | {s.get('reason')}")


        for other_player in self.game.players:
            if other_player == self:
                continue

            colours = set(p.colour for p in self.properties)
            for colour in colours:
                colour_props = [p for p in all_properties if p.colour == colour]
                self_props_of_colour = [p for p in self.properties if p.colour == colour]

                if len(self_props_of_colour) == len(colour_props) - 1:
                    missing_props = [p for p in colour_props if p.owner == other_player and p not in self_props_of_colour]
                    if not missing_props:
                        continue
                    desired_prop = missing_props[0]

                    trade_type = random.choice(['cash', 'property'])

                    if trade_type == 'cash':
                        required_cash = int(desired_prop.price * 1.5)

                        if self.money < required_cash:
                            unmortgage_candidates = [
                                p for p in self.properties
                                if not p.mortgaged and p.houses == 0 and not p.hotel and p != desired_prop
                            ]
                            for prop_to_mortgage in unmortgage_candidates:
                                if self.money >= required_cash:
                                    break
                                self.mortgage_property(prop_to_mortgage)

                        if self.money >= required_cash:
                            print(f"{self.name} offers £{required_cash} cash to {other_player.name} for {desired_prop.name} (worth £{desired_prop.price})")
                            self.money -= required_cash
                            other_player.money += required_cash
                            if not self.ensure_non_negative_balance():  # Added after trade
                               return False                            

                            desired_prop.owner = self
                            other_player.properties.remove(desired_prop)
                            self.properties.append(desired_prop)
                            self.ensure_non_negative_balance()
                            if self._owns_full_colour_set(desired_prop.colour) and desired_prop.colour not in self._announced_sets:
                                print(f"✨ {self.name} now owns all {desired_prop.colour} properties!")
                                self._announced_sets.add(desired_prop.colour)

                            print(f"Trade complete: {self.name} now owns {desired_prop.name}.")
                            return True
                        else:
                            continue

                    else:  # trade_type == 'property'
                        my_props = [p for p in self.properties if p != desired_prop]
                        needed_value = int(desired_prop.price * 1.25)

                        for r in range(1, len(my_props) + 1):
                            for combo in combinations(my_props, r):
                                combo_value = sum(p.price for p in combo)

                                if combo_value >= needed_value:
                                    breaking_set = False
                                    warned = False  # To show warning only once

                                    # Check if trading away any property breaks a full set
                                    post_trade_props = [p for p in self.properties if p not in combo] + [desired_prop]
                                    for colour in set(p.colour for p in self.properties):
                                       full_set = [tile for tile in self.board if isinstance(tile, Property) and tile.colour == colour]
                                       owns_full_set_now = all(p in self.properties for p in full_set)
                                       owns_full_set_after = all(p in post_trade_props for p in full_set)

                                       if owns_full_set_now and not owns_full_set_after:
                                          print(f"⚠️ Trade blocked: {self.name} would lose their full {colour} colour set!")
                                          breaking_set = True
                                          break
                                    

                                    # Also check if desired property's colour set would be broken
                                    desired_colour_props = [tile for tile in self.board if isinstance(tile, Property) and tile.colour == desired_prop.colour]
                                    if all(prop in self.properties for prop in desired_colour_props):
                                        if any(p.colour == desired_prop.colour for p in combo):
                                            if not warned:
                                                print(f"⚠️ Trade blocked: {self.name} would lose their {desired_prop.colour} colour set!")
                                                warned = True
                                            breaking_set = True

                                    if breaking_set:
                                        continue

                                    # No breaking, perform trade
                                    offered_names = ', '.join(p.name for p in combo)
                                    print(f"{self.name} offers {offered_names} (worth £{combo_value}) to {other_player.name} for {desired_prop.name} (worth £{desired_prop.price})")

                                    for p in combo:
                                        p.owner = other_player
                                        self.properties.remove(p)
                                        other_player.properties.append(p)

                                    desired_prop.owner = self
                                    other_player.properties.remove(desired_prop)
                                    self.properties.append(desired_prop)

                                    if self._owns_full_colour_set(desired_prop.colour) and desired_prop.colour not in self._announced_sets:
                                        print(f"✨ {self.name} now owns all {desired_prop.colour} properties!")
                                        self._announced_sets.add(desired_prop.colour)
                                    

                                    print(f"Trade complete: {self.name} now owns {desired_prop.name}.")
                                    mortgaged_props_self = [p.name for p in self.properties if p.mortgage]
                                    if mortgaged_props_self:
                                      print(f"💤 {self.name} has properties: {', '.join(mortgaged_props_self)}")

                                    mortgaged_props_other = [p.name for p in other_player.properties if p.mortgage]
                                    if mortgaged_props_other:
                                      print(f"💤 {other_player.name} has properties: {', '.join(mortgaged_props_other)}")

    
                                    return True

        return False
    
    def move(self):

        if self.in_jail:
         agent = getattr(self.game, "agent", None)
         if agent is not None:
            jail_sugg = agent.suggest_jail_action(self, self.game)
            print(f"AGENT SUGGESTION — Jail action: {jail_sugg['action']} "
                  f"(score={jail_sugg.get('score',0):.2f}) — {jail_sugg.get('reason')}")


            print(f"{self.name} is in jail (Turn {self.jail_turns + 1}/3).")
            die1, die2 = self.roll_dice()
            if die1 == die2:
                print(f"{self.name} rolled doubles and is released from jail!")
                self.in_jail = False
                self.jail_turns = 0
                self.position = (self.position + die1 + die2) % len(self.board)
                self.handle_tile()
            else:
                self.jail_turns += 1
                if self.jail_turns >= 3:
                    print(f"{self.name} pays £50 to get out of jail and lands on {self.board[self.position+ die1 + die2]}")
                    self.money -= 50
                    self.in_jail = False
                    self.jail_turns = 0
                    self.position = (self.position + die1 + die2) % len(self.board)
                    self.handle_tile()
                else:
                    print(f"{self.name} stays in jail.")
            return

        total_steps = 0
        self.doubles_count = 0

        while True:
            die1, die2 = self.roll_dice()
            steps = die1 + die2
            total_steps += steps

            if die1 == die2:
                self.doubles_count += 1
                if self.doubles_count == 3:
                    print(f"{self.name} rolled three doubles in a row and is sent to jail!")
                    self.go_to_jail()
                    return
                print(f"{self.name} rolled doubles and will roll again!")
                continue
            else:
                break

        prev_position = self.position
        self.position = (self.position + total_steps) % len(self.board)

        if self.position < prev_position:
            print(f"{self.name} passed Go and collects £200!")
            self.money += 200

        print(f"{self.name} lands on {self.board[self.position]}")
        self.handle_tile()


    def build_houses(self):
        """Build houses on most expensive color sets, maintaining £150 minimum balance"""
        MIN_RESERVE = 150
        MAX_HOUSES_PER_TURN = 6
        agent = getattr(self.game, "agent", None)
        if agent is not None:
    # prepare candidate_props: dict colour -> [prop,...] for full sets
          candidate_props = {}
          for prop in self.properties:
            if prop.buildable and not prop.mortgaged and self._owns_full_colour_set(prop.colour):
              candidate_props.setdefault(prop.colour, []).append(prop)
          if candidate_props:
             build_suggestions = agent.suggest_build(self, candidate_props, self.game)
             print("AGENT BUILD SUGGESTIONS:")
             for s in build_suggestions[:3]:
              print(f"  - {s.get('colour','?')}: {s.get('reason')}")
        
        # Check if player can afford to build
        if self.money <= MIN_RESERVE:
            print(f"{self.name} can't build - needs minimum £{MIN_RESERVE} reserve")
            return

        # 1. Identify complete, buildable color sets
        color_sets = defaultdict(list)
        for prop in self.properties:
            if (prop.buildable and not prop.mortgaged 
                and self._owns_full_colour_set(prop.colour)):
                color_sets[prop.colour].append(prop)
        
        if not color_sets:
            print(f"{self.name} has no complete color sets to build on")
            return

        # 2. Sort sets by most expensive first (Dark Blue £200 -> Brown £50)
        build_order = sorted(color_sets.keys(),
                           key=lambda c: -color_sets[c][0].house_price)
        
        total_built = 0
        for color in build_order:
            if total_built >= MAX_HOUSES_PER_TURN:
                break
                
            props = color_sets[color]
            house_price = props[0].house_price
            available_houses = min(
                MAX_HOUSES_PER_TURN - total_built,
                (self.money - MIN_RESERVE) // house_price
            )
            
            if available_houses < 1:
                continue
                
            print(f"\nBuilding on {color} set (£{house_price}/house)...")
            
            # 3. Build houses with even distribution
            houses_built = 0
            while (houses_built < available_houses 
                   and self.money >= MIN_RESERVE + house_price):
                
                # Find buildable property with fewest houses
                buildable_props = [p for p in props 
                                 if p.can_build_house() or p.can_build_hotel()]
                if not buildable_props:
                    break
                    
                target = min(buildable_props,
                            key=lambda p: p.houses if not p.hotel else float('inf'))
                
                # Prefer hotel conversion if possible
                if target.can_build_hotel():
                    target.add_hotel()
                    self.money -= house_price
                    houses_built += 1
                    total_built += 1
                    print(f"  Converted to HOTEL on {target.name} (£{house_price})")
                elif target.add_house():
                    self.money -= house_price
                    houses_built += 1
                    total_built += 1
                    print(f"  Added house on {target.name} (now {target.houses}) £{house_price}")
                else:
                    break
        
        if total_built > 0:
            print(f"\n{self.name} built {total_built} houses/hotels")
            print(f"Remaining balance: £{self.money}")
        else:
            print(f"{self.name} couldn't build while maintaining £{MIN_RESERVE} reserve")
    def sell_houses(self, target_amount=0):
        """Sell houses/hotels incrementally to raise specific amount"""
        SELL_RATIO = 0.5  # Houses sell for half price
        total_raised = 0
        
        # Sort properties by most expensive first (will sell these first)
        sellable_props = sorted(
            [p for p in self.properties if p.houses > 0 or p.hotel],
            key=lambda p: -p.house_price
        )

        for prop in sellable_props:
            while ((target_amount == 0 or total_raised < target_amount) 
                   and (prop.houses > 0 or prop.hotel)):
                
                sell_value = int(prop.house_price * SELL_RATIO)
                
                if prop.hotel:
                    # Convert hotel to 4 houses first
                    prop.hotel = False
                    prop.houses = 4
                    print(f"Converted hotel to 4 houses on {prop.name}")
                    continue
                    
                # Sell one house at a time
                prop.houses -= 1
                self.money += sell_value
                total_raised += sell_value
                print(f"Sold 1 house on {prop.name} for £{sell_value} "
                      f"(now {prop.houses} houses)")
                
                # Immediate balance update check
                if target_amount > 0 and total_raised >= target_amount:
                    break
        
        return total_raised

    def build_houses(self, colour = None):
        """Smart building with selling and fund reallocation"""
        MIN_RESERVE = 150
        BUILD_BUFFER = 50  # Extra cushion for building
        
        # 1. Check cheapest available build options
        buildable_sets = defaultdict(list)
        for prop in self.properties:
            if (prop.buildable and not prop.mortgaged 
                and self._owns_full_colour_set(prop.colour)):
                if colour is None or prop.colour == colour:
                    buildable_sets[prop.house_price].append(prop)
        
        if not buildable_sets:
            return False

        cheapest_price = min(buildable_sets.keys())
        cheapest_props = buildable_sets[cheapest_price]
        
        # 2. Try building normally first
        built_count = 0
        while self.money >= MIN_RESERVE + cheapest_price + BUILD_BUFFER:
            target = min(cheapest_props, 
                        key=lambda p: p.houses if not p.hotel else float('inf'))
            
            if target.hotel:
                break
                
            if target.houses == 4 and target.can_build_hotel():
                if self.money >= MIN_RESERVE + cheapest_price:
                    target.add_hotel()
                    self.money -= cheapest_price
                    built_count += 1
                    print(f"Built hotel on {target.name}")
            elif target.add_house():
                self.money -= cheapest_price
                built_count += 1
                print(f"Built house on {target.name} (now {target.houses})")
            else:
                break
        
        if built_count > 0:
            return True
            
        # 3. If couldn't build, try selling expensive to fund cheap builds
        if (self.money < MIN_RESERVE + cheapest_price and random.random() < 0.1):
            print("Considering selling houses to fund building ...")
            needed = max(cheapest_price, 
                        (MIN_RESERVE + cheapest_price) - self.money)
          
            # Sell from most expensive properties first
            expensive_props = sorted(
                [p for p in self.properties if p.houses > 0 or p.hotel],
                key=lambda p: -p.house_price
            )
            
            for prop in expensive_props:
                if self.money >= MIN_RESERVE + cheapest_price:
                    break
                    
                while (prop.houses > 0 or prop.hotel) and \
                      self.money < MIN_RESERVE + cheapest_price:
                        
                    sell_value = int(prop.house_price * 0.5)
                    
                    if prop.hotel:
                        prop.hotel = False
                        prop.houses = 4
                        print(f"Converted hotel to 4 houses on {prop.name}")
                        continue
                        
                    prop.houses -= 1
                    self.money += sell_value
                    print(f"Sold 1 house from {prop.name} (+£{sell_value})")
                    
                    # Immediately try building with new funds
                    if self.money >= MIN_RESERVE + cheapest_price:
                        return self.build_houses()  # Recursively retry
        
        return False
        
    def ensure_non_negative_balance(self):
        """Handle bankruptcy with proper asset valuation"""
        original_balance = self.money
        
        # 1. Try selling houses/hotels first
        if self.money < 0:
            print(f"\n🚨 {self.name} has negative balance (£{self.money}) - attempting recovery...")
            houses_sold = self.sell_houses(target_amount=abs(self.money))
            if houses_sold > 0:
                print(f"Sold buildings to raise £{houses_sold}")
                if self.money >= 0:
                    return True

        # 2. Try mortgaging properties
        mortgaged_props = []
        for prop in self.properties:
            if self.money >= 0:
                break
            if not prop.mortgaged and prop.houses == 0 and not prop.hotel:
                if self.mortgage_property(prop):
                    mortgaged_props.append(prop.name)
                    print(f"Mortgaged {prop.name} for £{prop.mortgage_value}")

        # 3. Final bankruptcy check
        if self.money < 0:
            print(f"\n💀 {self.name} is BANKRUPT! (Balance: £{self.money}) 💀")
            self.declare_bankrupt()
            return False
        
        if original_balance != self.money:
            print(f"{self.name}'s new balance: £{self.money}")
        return True

    def declare_bankrupt(self):
        """Handle player bankruptcy and determine winner"""
        print("\n⚖️ Calculating final standings...")
        
        # Calculate all players' net worth
        leaderboard = []
        for player in self.game.players:
            if player != self and player.money >= 0:  # Skip bankrupt players
                net_worth = self.calculate_net_worth(player)
                leaderboard.append((player, net_worth))
                print(f"  {player.name}: £{net_worth} total worth")

        if not leaderboard:
            print("All players bankrupt - no winner!")
            exit()

        # Sort by net worth descending
        leaderboard.sort(key=lambda x: -x[1])
        winner = leaderboard[0][0]
        winner_worth = leaderboard[0][1]

        print(f"\n🏆 {winner.name} WINS!")
        print(f"  Cash: £{winner.money}")
        print(f"  Property value: £{winner_worth-winner.money}")
        print(f"  Total net worth: £{winner_worth}")
        exit()

    def calculate_net_worth(self, player):
        """Calculate player's total net worth including assets"""
        total = player.money
        
        # Property values
        for prop in player.properties:
            if prop.mortgaged:
                total += prop.mortgage_value  # Already half of price
            else:
                total += prop.price  # Full value if unmortgaged
            
            # House/hotel values (half of build cost)
            if prop.hotel:
                total += prop.house_price * 2  # Hotel = 4 houses
            elif prop.houses > 0:
                total += prop.houses * prop.house_price * 0.5
        
        return total

    def handle_tile(self):
        tile = self.board[self.position]
        if isinstance(tile, Property):
            if tile.owner is None:
                agent = getattr(self.game, "agent", None)
                suggestion = None
                if agent:
                    suggestion = agent.suggest_buy(self, tile, self.game)
                    print(f"AGENT SUGGESTION — Buy {tile.name}? -> {suggestion['action'].upper()} (score={suggestion.get('score',0):.2f}) — {suggestion.get('reason')}")
                if self.human:
                    choice = input(f"Do you want to buy {tile.name} for £{tile.price}? (yes/no) ").lower()
                    if choice in ['yes', 'y']:
                        self.buy_property(tile)
                    else:
                        self.auction_property(tile)
                else:
                    if suggestion and suggestion['action'] == 'buy':
                        self.buy_property(tile)
                    else:
                        self.auction_property(tile)
            elif tile.owner != self:
                roll_dice = self.last_roll_total if tile.colour == "Utility" else None
                owns_full_set = tile.owner._owns_full_colour_set(tile.colour)
                rent = tile.calculate_rent(owns_full_colour_set=owns_full_set, roll_dice=roll_dice)
                print(f"{self.name} pays £{rent} rent to {tile.owner.name}")
                self.money -= rent
                tile.owner.money += rent
                self.ensure_non_negative_balance()
            else:
                print(f"{self.name} owns this property")
        elif tile in ["Chance", "Community Chest"]:
            self.draw_card(tile)
        elif tile == "Go To Jail":
            self.go_to_jail()
        elif tile == "Income Tax":
            self.money -= 200
            print(f"Paid £200 Income Tax. Balance: £{self.money}")
            self.ensure_non_negative_balance()
        elif tile == "Super Tax":
            self.money -= 100
            print(f"Paid £100 Super Tax. Balance: £{self.money}")
            self.ensure_non_negative_balance()

            
    def draw_card(self, deck_type):
        """Draw a Chance or Community Chest card (simplified)"""
        card = random.choice([
            ("Bank error in your favor, gain £200", 200),
            ("Doctor's fees, lose £50", -50),
            ("From sale of stock, gain £50", 50),
            ("Go to Jail", "jail"),
            ("Grand Opera Night, pay £100", -100),
            ("Income tax refund, gain £20", 20)
        ])
        
        print(f"{deck_type} Card: {card[0]}")
        
        if card[1] == "jail":
            self.go_to_jail()
        else:
            self.money += card[1]
            print(f"New balance: £{self.money}")
            if self.money < 0:
                if not self.ensure_non_negative_balance():
                    return

    def __str__(self):
        pos_name = self.board[self.position].name if isinstance(self.board[self.position], Property) else self.board[self.position]
        return (f"{self.name} (£{self.money}) at {pos_name} | Properties: {len(self.properties)}")
    

    def get_candidate_builds(self):
        candidate = {}
        for colour in set(p.colour for p in self.properties):
          if self._owns_full_colour_set(colour):
            props_in_colour = [p for p in self.properties if p.colour == colour]
            candidate[colour] = props_in_colour
        return candidate