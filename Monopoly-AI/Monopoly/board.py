# Monopoly/board.py

from Monopoly.property import Property

tiles = [
    "Go",
    Property("Old Kent Road", 60, 2, "Brown", [2, 10, 30, 90, 160, 250]),
    "Community Chest",
    Property("Whitechapel Road", 60, 4, "Brown", [4, 20, 60, 180, 320, 450]),
    "Income Tax",
    Property("King's Cross Station", 200, 25, "Station"),  # Rent logic handled separately
    Property("The Angel Islington", 100, 6, "Light Blue", [6, 30, 90, 270, 400, 550]),
    "Chance",
    Property("Euston Road", 100, 6, "Light Blue", [6, 30, 90, 270, 400, 550]),
    Property("Pentonville Road", 120, 8, "Light Blue", [8, 40, 100, 300, 450, 600]),
    "Jail",
    Property("Pall Mall", 140, 10, "Pink", [10, 50, 150, 450, 625, 750]),
    Property("Electric Company", 150, 10, "Utility"),  # Rent handled via dice roll
    Property("Whitehall", 140, 10, "Pink", [10, 50, 150, 450, 625, 750]),
    Property("Northumberland Avenue", 160, 12, "Pink", [12, 60, 180, 500, 700, 900]),
    Property("Marylebone Station", 200, 25, "Station"),
    Property("Bow Street", 180, 14, "Orange", [14, 70, 200, 550, 750, 950]),
    "Community Chest",
    Property("Marlborough Street", 180, 14, "Orange", [14, 70, 200, 550, 750, 950]),
    Property("Vine Street", 200, 16, "Orange", [16, 80, 220, 600, 800, 1000]),
    "Free Parking",
    Property("Strand", 220, 18, "Red", [18, 90, 250, 700, 875, 1050]),
    "Chance",
    Property("Fleet Street", 220, 18, "Red", [18, 90, 250, 700, 875, 1050]),
    Property("Trafalgar Square", 240, 20, "Red", [20, 100, 300, 750, 925, 1100]),
    Property("Fenchurch Street Station", 200, 25, "Station"),
    Property("Leicester Square", 260, 22, "Yellow", [22, 110, 330, 800, 975, 1150]),
    Property("Coventry Street", 260, 22, "Yellow", [22, 110, 330, 800, 975, 1150]),
    Property("Water Works", 150, 10, "Utility"),
    Property("Piccadilly", 280, 24, "Yellow", [24, 120, 360, 850, 1025, 1200]),
    "Go To Jail",
    Property("Regent Street", 300, 26, "Green", [26, 130, 390, 900, 1100, 1275]),
    Property("Oxford Street", 300, 26, "Green", [26, 130, 390, 900, 1100, 1275]),
    "Community Chest",
    Property("Bond Street", 320, 28, "Green", [28, 150, 450, 1000, 1200, 1400]),
    Property("Liverpool Street Station", 200, 25, "Station"),
    "Chance",
    Property("Park Lane", 350, 35, "Dark Blue", [35, 175, 500, 1100, 1300, 1500]),
    "Super Tax",
    Property("Mayfair", 400, 50, "Dark Blue", [50, 200, 600, 1400, 1700, 2000])
]
