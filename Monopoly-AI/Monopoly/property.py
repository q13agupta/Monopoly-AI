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
        "Station": 0,
        "Utility": 0
    }

    def __init__(self, name, price, base_rent, colour, rent_levels=None):
        self.name = name
        self.price = price
        self.base_rent = base_rent
        self.colour = colour
        self.house_price = self.house_price_map.get(colour, 0)
        self.buildable = colour not in ["Station", "Utility"]
        self.owner = None
        self.houses = 0  # 0–4 houses
        self.hotel = False  # Replaces 4 houses
        self.mortgaged = False
        # rent_levels format: [no houses, 1h, 2h, 3h, 4h, hotel]
        self.rent_levels = rent_levels if rent_levels else []

    def calculate_rent(self, owns_full_colour_set=False, roll_dice=None):
        """Calculate rent with strict Monopoly rules."""
        if self.mortgaged or not self.owner:
            return 0

        # Utilities
        if self.colour == "Utility":
            if roll_dice is None:
                return 0
            owned_utils = sum(1 for p in self.owner.properties if p.colour == "Utility")
            multiplier = 4 if owned_utils == 1 else 10
            return roll_dice * multiplier

        # Stations
        if self.colour == "Station":
            owned_stations = sum(1 for p in self.owner.properties if p.colour == "Station")
            return [25, 50, 100, 200][owned_stations - 1]

            # Street properties
        if self.hotel:
         return self.rent_levels[-1] if self.rent_levels else self.base_rent * 10
    
        if self.houses > 0:
         return self.rent_levels[self.houses] if self.rent_levels else self.base_rent * (self.houses + 1)
    
         # Base rent (only case where doubling applies)
        base_rent = self.rent_levels[0] if self.rent_levels else self.base_rent
        return base_rent * (2 if owns_full_colour_set else 1)

    # --- Property Management Methods ---
    def can_build_house(self):
        """Check if house can be added following all rules."""
        return (
            self.buildable
            and not self.mortgaged
            and not self.hotel
            and self.houses < 4
        )

    def add_house(self):
        """Strict house addition with validation."""
        if not self.can_build_house():
            return False
        self.houses += 1
        return True

    def can_build_hotel(self):
        """Check if 4 houses can convert to hotel."""
        return (
            self.buildable
            and not self.mortgaged
            and self.houses == 4
            and not self.hotel
        )

    def add_hotel(self):
        """Convert 4 houses to hotel with validation."""
        if not self.can_build_hotel():
            return False
        self.houses = 0
        self.hotel = True
        return True

    # --- Mortgage Methods ---
    def can_mortgage(self):
        return not self.mortgaged and self.houses == 0 and not self.hotel

    def mortgage(self):
        if not self.can_mortgage():
            return False
        self.mortgaged = True
        return True

    def unmortgage_cost(self):
        return int(self.mortgage_value * 1.1)

    # --- Property Information ---
    @property
    def mortgage_value(self):
        return self.price // 2

    def __str__(self):
        status = []
        if self.mortgaged:
            status.append("mortgaged")
        if self.houses:
            status.append(f"{self.houses} house(s)")
        if self.hotel:
            status.append("HOTEL")
        return f"{self.name}{' (' + ', '.join(status) + ')' if status else ''}"
    
    def to_dict(self):
        return {
            "name": self.name,
            "price": self.price,
            "owner": getattr(self.owner, "name", None),
            "colour": self.colour,
            "houses": self.houses,
            "hotel": self.hotel,
            "mortgaged": self.mortgaged,
            "buildable": self.buildable,
            "house_price": self.house_price
        }

    def expected_rent(self, p_land, owns_full_colour_set=False, expected_roll=7):
        """Return expected rent per-visit, scaled by landing probability p_land (0..1)."""
        if self.mortgaged or self.owner is None:
            return 0.0
        if self.colour == "Utility":
            owned_utils = sum(1 for p in self.owner.properties if p.colour == "Utility")
            multiplier = 4 if owned_utils == 1 else 10
            rent = expected_roll * multiplier
            return p_land * rent
        if self.colour == "Station":
            owned = sum(1 for p in self.owner.properties if p.colour == "Station")
            rent = [25, 50, 100, 200][max(0, owned - 1)]
            return p_land * rent
        if self.hotel:
            rent = self.rent_levels[-1] if self.rent_levels else self.base_rent * 10
        elif self.houses > 0:
            rent = self.rent_levels[self.houses] if self.rent_levels else self.base_rent * (self.houses + 1)
        else:
            base = self.rent_levels[0] if self.rent_levels else self.base_rent
            rent = base * (2 if owns_full_colour_set else 1)
        return p_land * rent

    def build_cost(self):
        return self.house_price if self.buildable else None
