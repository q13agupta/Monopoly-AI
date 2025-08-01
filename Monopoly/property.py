class Property:
    house_price_map = {
        "Brown": 50,
        "Light Blue": 50,
        "Pink": 100,
        "Orange": 100,
        "Red": 150,
        "Yellow": 150,
        "Green": 200,
        "Dark Blue": 200,
        "Station": 0,   # No houses allowed
        "Utility": 0    # No houses allowed
    }

    def __init__(self, name, price, rent, colour, house_price=0, buildable=True, house_rents=None, hotel_rent=0):
        self.name = name
        self.price = price
        self.rent = rent
        self.colour = colour
        self.house_price = house_price
        self.buildable = buildable  # False for utilities/stations
        self.owner = None
        self.houses = 0
        self.hotel = False
        self.house_rents = house_rents if house_rents else []
        self.hotel_rent = hotel_rent

    def __str__(self):
        return self.name  # So print(f"Lands on {property}") shows the name

    @property
    def mortgage_value(self):
        return self.price * 0.5

    def mortgage(self):
        if self.mortgaged:
            print(f"{self.name} is already mortgaged.")
            return False
        if self.houses > 0 or self.hotel:
            print(f"Cannot mortgage {self.name} with houses/hotel built.")
            return False
        self.mortgaged = True
        print(f"{self.name} has been mortgaged for £{self.mortgage_value:.2f}")
        return True

    def unmortgage(self):
        if not self.mortgaged:
            print(f"{self.name} is not mortgaged.")
            return False
        cost = self.mortgage_value * 1.1
        self.mortgaged = False
        print(f"{self.name} has been unmortgaged by paying £{cost:.2f}")
        return cost

    
    def calculate_rent(self, owns_full_colour_set=False, dice_roll=None):
        # Utilities
        if self.colour == "Utility":
            if dice_roll is None:
                return 0
            owned_utilities = [p for p in self.owner.properties if p.colour == "Utility"]
            multiplier = 4 if len(owned_utilities) == 1 else 10
            return multiplier * dice_roll

        # Stations
        if self.colour == "Station":
            owned_stations = [p for p in self.owner.properties if p.colour == "Station"]
            return 25 * (2 ** (len(owned_stations) - 1))

        if self.colour not in ["Utility", "Station"]:
         if self.hotel:
            return 40 * self.rent
        elif self.houses > 0:
            return 5 * self.houses * self.rent
        else:
            return self.rent * 2 if owns_full_colour_set else self.rent
        

    def can_build(self):
        # Disallow building on Station or Utility
        if self.colour in ["Station", "Utility"]:
            return False
        return not self.mortgaged and not self.hotel

    def build_house(self):
        if not self.buildable:

            return False
        if self.hotel:
            print(f"Hotel already built on {self.name}.")
            return False
        if self.houses < 4:
            self.houses += 1
            return True
        elif self.houses == 4 and not self.hotel:
            self.houses = 0
            self.hotel = True
            return True
        return False





    def calculate_rent(self, owns_full_colour_set=False, dice_roll=None):
        # Utilities
        if self.colour == "Utility":
            if dice_roll is None:
                return 0
            owned_utilities = [p for p in self.owner.properties if p.colour == "Utility"]
            multiplier = 4 if len(owned_utilities) == 1 else 10
            return multiplier * dice_roll

        # Stations
        if self.colour == "Station":
            owned_stations = [p for p in self.owner.properties if p.colour == "Station"]
            return 25 * (2 ** (len(owned_stations) - 1))

        # Streets
        if self.hotel:
            return self.hotel_rent
        elif self.houses > 0:
            return self.house_rents[self.houses - 1]
        else:
            return self.rent * 2 if owns_full_colour_set else self.rent
