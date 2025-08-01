import random
from Monopoly.property import Property

class Player:
    def __init__(self, name="Player", board=None):
        self.name = name
        self.position = 0
        self.money = 1500
        self.in_jail = False
        self.jail_turns = 0
        self.doubles_count = 0
        self.board = board if board else []
        self.properties = []

    def roll_dice(self):
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        print(f"{self.name} rolls: {die1} + {die2} = {die1 + die2}")
        return die1, die2

    def go_to_jail(self):
        print(f"{self.name} is sent to jail!")
        self.position = 10  # Jail tile index
        self.in_jail = True
        self.jail_turns = 0
        self.doubles_count = 0

    def _owns_full_colour_set(self, colour):
        """Check if player owns all properties of a given colour"""
        colour_props = [tile for tile in self.board 
                       if isinstance(tile, Property) and tile.colour == colour]
        return all(prop.owner == self for prop in colour_props)

    def buy_property(self, property_tile):
        """Attempt to buy a property tile"""
        if self.money >= property_tile.price:
            print(f"{self.name} buys {property_tile.name} for £{property_tile.price}")
            self.money -= property_tile.price
            property_tile.owner = self
            self.properties.append(property_tile)
            print(f"New balance: £{self.money}")
            if self._owns_full_colour_set(property_tile.colour):
                print(f"✨ {self.name} now owns all {property_tile.colour} properties!")
            return True
        else:
            print(f"{self.name} cannot afford {property_tile.name}")
            return False
    def _can_build_evenly(self, property_to_build, colour_props):
        """
        Enforce even building rule: difference in building levels
        across properties in the colour group ≤ 1.
        Hotels count as 5 houses for leveling.
        """
        levels = []
        for p in colour_props:
            if p.hotel:
                levels.append(5)
            else:
                levels.append(p.houses)

        current_level = 5 if property_to_build.hotel else property_to_build.houses
        if current_level == 5:
            return False  # Can't build more if hotel already built

        levels_without = [lvl for p, lvl in zip(colour_props, levels) if p != property_to_build]

        if not levels_without:
            return True  # Only one property in group, always can build

        new_level = current_level + 1
        new_levels = levels_without + [new_level]

        return max(new_levels) - min(new_levels) <= 1        
    def build(self, property_to_build):
        if property_to_build.owner != self:
            return False
        if not self._owns_full_colour_set(property_to_build.colour):
            return False
        
        cost = property_to_build.house_price
        if self.money < cost:
            return False
        
        success = property_to_build.build_house()
        if success:
            self.money -= cost
            print(f"{self.name} paid £{cost} to build on {property_to_build.name}. Remaining money: £{self.money}")
            return True
        return False
    
    def propose_trade(self, other, offered_props, requested_props, cash_offer=0, cash_request=0):
        if any(p.owner != self for p in offered_props):
            return False
        if any(p.owner != other for p in requested_props):
            print(f"{other.name} doesn't own all requested properties.")
            return False
        if self.money < cash_offer:
            return False
        if other.money < cash_request:
            print(f"{other.name} can't afford the cash requested.")
            return False
        
        offered_value = sum(p.price for p in offered_props)
        requested_value = sum(p.price for p in requested_props)
        
        if cash_offer > 0 and offered_value == 0:
            if cash_offer < 1.5 * requested_value:
                print ("Inadequate funds offered")
                return False
        
        if cash_offer == 0 and cash_request == 0:
            if offered_value < requested_value:
                print ("Stop trying to swindle me")
                return False
        
        print(f"{self.name} trades {', '.join(p.name for p in offered_props)} + £{cash_offer} to {other.name} "
              f"for {', '.join(p.name for p in requested_props)} + £{cash_request}")
        
        for p in offered_props:
            p.owner = other
            self.properties.remove(p)
            other.properties.append(p)
        for p in requested_props:
            p.owner = self
            other.properties.remove(p)
            self.properties.append(p)
        
        self.money -= cash_offer
        other.money += cash_offer
        other.money -= cash_request
        self.money += cash_request
        
        return True
    
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
    
    def unmortgage_property(self, property_to_unmortgage):
        if property_to_unmortgage.owner != self:
            return False
        if not property_to_unmortgage.mortgaged:
            return False
        
        cost = property_to_unmortgage.unmortgage()
        if self.money < cost:
            print(f"{self.name} cannot afford to unmortgage {property_to_unmortgage.name}. Needs £{cost:.2f}, has £{self.money}.")
            return False
        self.money -= cost
        print(f"{self.name} paid £{cost:.2f} to unmortgage {property_to_unmortgage.name}. Remaining money: £{self.money}")
        return True


    def attempt_trade(self):
        """
        Attempt to trade for missing properties in owned colour groups.
        Buys the missing property at 1.5× price if affordable.
        """
        for tile in self.board:
            if isinstance(tile, Property) and tile.colour:
                # Skip properties already owned by this player
                if tile.owner == self:
                    continue
                
                # Check if player owns all but one in the colour group
                same_colour = [t for t in self.board 
                               if isinstance(t, Property) and t.colour == tile.colour]
                owned_by_self = [t for t in same_colour if t.owner == self]
                
                if len(owned_by_self) == len(same_colour) - 1:
                    # Find missing property owned by another player
                    missing_prop = next((t for t in same_colour 
                                       if t not in owned_by_self and t.owner), None)
                    if missing_prop:
                        seller = missing_prop.owner
                        trade_price = int(1.5 * missing_prop.price)
                        
                        if self.money >= trade_price:
                            print(f"{self.name} buys {missing_prop.name} from {seller.name} for £{trade_price}")
                            self.money -= trade_price
                            seller.money += trade_price
                            missing_prop.owner = self
                            self.properties.append(missing_prop)
                            seller.properties.remove(missing_prop)
                            
                            if self._owns_full_colour_set(tile.colour):
                                print(f"✨ {self.name} now owns all {tile.colour} properties!")
                            return True
        return False

    def move(self):
        if self.in_jail:
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
                    print(f"{self.name} pays £50 to get out of jail.")
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
    def calculate_rent(self, property_tile):
        if property_tile.owner is None or property_tile.owner == self or property_tile.mortgaged:
            return 0
        
        base_rent = property_tile.rent
        if property_tile.hotel:
            return property_tile.hotel_rent
        elif property_tile.houses > 0:
            return property_tile.house_rents[property_tile.houses - 1]
        else:
            # No houses or hotels - check if owner owns full set to double rent
            if self._owns_full_colour_set(property_tile.colour):
                return base_rent * 2
            return base_rent


    def handle_tile(self):
        tile = self.board[self.position]

        if isinstance(tile, Property):
            if tile.owner is None:
                self.buy_property(tile)
            elif tile.owner != self:
                rent = tile.calculate_rent(self._owns_full_colour_set(tile.colour))
                print(f"{self.name} pays £{rent} rent to {tile.owner.name}")
                self.money -= rent
                tile.owner.money += rent
            else:
                print(f"{self.name} owns this property")

        elif tile in ["Chance", "Community Chest"]:
            self.draw_card(tile)
        elif tile == "Go To Jail":
            self.go_to_jail()
        elif tile == "Income Tax":
            self.money -= 200
            print(f"Paid £200 Income Tax. Balance: £{self.money}")
        elif tile == "Super Tax":
            self.money -= 100
            print(f"Paid £100 Super Tax. Balance: £{self.money}")

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


    def __str__(self):
        pos_name = self.board[self.position].name if isinstance(self.board[self.position], Property) else self.board[self.position]
        return (f"{self.name} (£{self.money}) at {pos_name} | Properties: {len(self.properties)}")
