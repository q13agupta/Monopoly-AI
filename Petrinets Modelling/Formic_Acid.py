# formic_petri_net.py
from copy import deepcopy

class ColouredToken:
    def __init__(self, type, amount=1.0):
        self.type = type
        self.amount = amount

    def __repr__(self):
        return f"{self.type}({self.amount})"

class Place:
    def __init__(self, name):
        self.name = name
        self.tokens = []

    def add_tokens(self, tokens):
        if isinstance(tokens, list):
            self.tokens.extend(tokens)
        else:
            self.tokens.append(tokens)

    def remove_tokens(self, type=None, amount=None):
        """Simplified removal - remove all tokens of specific type or all tokens"""
        if type:
            # Remove tokens of specific type
            removed = [t for t in self.tokens if t.type == type]
            self.tokens = [t for t in self.tokens if t.type != type]
            if amount:
                # If amount specified, only remove that amount
                total_removed = sum(t.amount for t in removed)
                if total_removed > amount:
                    # Need to return some tokens
                    remaining = total_removed - amount
                    self.tokens.extend([ColouredToken(type, remaining)])
                    return [ColouredToken(type, amount)]
            return removed
        else:
            # Remove all tokens
            removed = self.tokens.copy()
            self.tokens.clear()
            return removed

    def count(self, type=None):
        if type:
            return sum(t.amount for t in self.tokens if t.type == type)
        return sum(t.amount for t in self.tokens)

class Transition:
    def __init__(self, name, func):
        self.name = name
        self.func = func

    def fire(self):
        self.func()

def build_formic_process():
    # -------------------------
    # Places
    # -------------------------
    P_feed_gas = Place("P_feed_gas")
    P_amine_feed = Place("P_amine_feed")
    P_reactor1 = Place("P_reactor1")
    P_HCOOH_Am = Place("P_HCOOH_Am")
    P_flash_vapour = Place("P_flash_vapour")
    P_flash_liquid = Place("P_flash_liquid")
    P_purge = Place("P_purge")
    P_recycle = Place("P_recycle")
    P_reactor2 = Place("P_reactor2")
    P_HCOOH_product = Place("P_HCOOH_product")
    P_amine_recycle = Place("P_amine_recycle")

    # -------------------------
    # Initial tokens
    # -------------------------
    P_feed_gas.add_tokens([
        ColouredToken("H2", 49),
        ColouredToken("CO2", 49),
        ColouredToken("N2", 2)
    ])
    P_amine_feed.add_tokens([ColouredToken("Am", 100)])

    # -------------------------
    # Feed transition - SIMPLIFIED
    # -------------------------
    def feed_to_reactor():
        """Move 10 mol of each component to reactor"""
        # Move 10 mol of each gas component
        for gas_type in ["H2", "CO2", "N2"]:
            if P_feed_gas.count(gas_type) >= 1:
                amount_to_move = min(10, P_feed_gas.count(gas_type))
                # Remove from feed
                P_feed_gas.remove_tokens(gas_type, amount_to_move)
                # Add to reactor
                P_reactor1.add_tokens(ColouredToken(gas_type, amount_to_move))
        
        # Move 10 mol of amine
        if P_amine_feed.count("Am") >= 1:
            amount_to_move = min(10, P_amine_feed.count("Am"))
            P_amine_feed.remove_tokens("Am", amount_to_move)
            P_reactor1.add_tokens(ColouredToken("Am", amount_to_move))

    def reaction1():
        """CO2 + H2 ↔ HCOOH, 90% conversion of CO2"""
        CO2_avail = P_reactor1.count("CO2")
        H2_avail = P_reactor1.count("H2")
        
        if CO2_avail > 0 and H2_avail > 0:
            # Determine limiting reactant
            limiting = min(CO2_avail, H2_avail)
            reacted = limiting * 0.9  # 90% conversion
            
            # Remove reacted reactants
            P_reactor1.remove_tokens("CO2", reacted)
            P_reactor1.remove_tokens("H2", reacted)
            
            # Add product
            P_reactor1.add_tokens(ColouredToken("HCOOH", reacted))
            
            # Add unreacted reactants back
            P_reactor1.add_tokens(ColouredToken("CO2", CO2_avail - reacted))
            P_reactor1.add_tokens(ColouredToken("H2", H2_avail - reacted))

    def reaction2():
        """HCOOH + Am → HCOOH·Am, 90% conversion of HCOOH"""
        HCOOH_avail = P_reactor1.count("HCOOH")
        Am_avail = P_reactor1.count("Am")
        
        if HCOOH_avail > 0 and Am_avail > 0:
            limiting = min(HCOOH_avail, Am_avail)
            reacted = limiting * 0.9  # 90% conversion
            
            # Remove reacted reactants
            P_reactor1.remove_tokens("HCOOH", reacted)
            P_reactor1.remove_tokens("Am", reacted)
            
            # Add product
            P_HCOOH_Am.add_tokens(ColouredToken("HCOOH·Am", reacted))
            
            # Add unreacted reactants back
            P_reactor1.add_tokens(ColouredToken("HCOOH", HCOOH_avail - reacted))
            P_reactor1.add_tokens(ColouredToken("Am", Am_avail - reacted))

    def flash():
        """Separate vapour and liquid phases"""
        # Move all gases to vapour
        for gas_type in ["CO2", "H2", "N2"]:
            amount = P_reactor1.count(gas_type)
            if amount > 0:
                P_reactor1.remove_tokens(gas_type, amount)
                P_flash_vapour.add_tokens(ColouredToken(gas_type, amount))
        
        # Move HCOOH and Am to liquid
        for liquid_type in ["HCOOH", "Am"]:
            amount = P_reactor1.count(liquid_type)
            if amount > 0:
                P_reactor1.remove_tokens(liquid_type, amount)
                P_flash_liquid.add_tokens(ColouredToken(liquid_type, amount))
        
        # Move HCOOH·Am to liquid
        hcooh_am_amount = P_HCOOH_Am.count("HCOOH·Am")
        if hcooh_am_amount > 0:
            P_HCOOH_Am.remove_tokens("HCOOH·Am", hcooh_am_amount)
            P_flash_liquid.add_tokens(ColouredToken("HCOOH·Am", hcooh_am_amount))

    def purge_recycle():
        """10% purge, 90% recycle"""
        total_vapour = P_flash_vapour.count()
        if total_vapour > 0:
            # Calculate amounts to purge and recycle
            purge_amount = total_vapour * 0.1
            recycle_amount = total_vapour * 0.9
            
            # Remove all vapour
            vapour_tokens = P_flash_vapour.remove_tokens()
            
            # Distribute to purge and recycle proportionally
            for token in vapour_tokens:
                purge_portion = (token.amount / total_vapour) * purge_amount
                recycle_portion = (token.amount / total_vapour) * recycle_amount
                
                if purge_portion > 0:
                    P_purge.add_tokens(ColouredToken(token.type, purge_portion))
                if recycle_portion > 0:
                    P_recycle.add_tokens(ColouredToken(token.type, recycle_portion))

    def reaction3():
        """Decompose HCOOH·Am → HCOOH + Am"""
        hcooh_am_amount = P_flash_liquid.count("HCOOH·Am")
        if hcooh_am_amount > 0:
            # Remove HCOOH·Am
            P_flash_liquid.remove_tokens("HCOOH·Am", hcooh_am_amount)
            # Add products
            P_HCOOH_product.add_tokens(ColouredToken("HCOOH", hcooh_am_amount))
            P_amine_recycle.add_tokens(ColouredToken("Am", hcooh_am_amount))

    # -------------------------
    # Define transitions
    # -------------------------
    transitions = [
        Transition("T0_feed", feed_to_reactor),
        Transition("T1_reaction1", reaction1),
        Transition("T2_reaction2", reaction2),
        Transition("T3_flash", flash),
        Transition("T4_purge_recycle", purge_recycle),
        Transition("T5_reaction3", reaction3)
    ]

    places = [
        P_feed_gas, P_amine_feed, P_reactor1, P_HCOOH_Am,
        P_flash_vapour, P_flash_liquid, P_purge, P_recycle,
        P_reactor2, P_HCOOH_product, P_amine_recycle
    ]

    return {"places": places, "transitions": transitions}