import random
import uuid
from collections import defaultdict, deque
from copy import deepcopy

# -------------------------
# Token, Place, Transition
# -------------------------

class ColouredToken:
    def __init__(self, ttype: str, batch_id: str = None, mass: float = 1.0, T: float = None, purity: float = None):
        self.type = ttype          # e.g., 'Ni_ore','CO','NiCO4','Ni_pure'
        self.batch_id = batch_id or str(uuid.uuid4())[:8]
        self.mass = mass
        self.T = T                 # temperature (C)
        self.purity = purity       # fraction 0..1
        self.time_in_process = 0.0

    def copy(self):
        return deepcopy(self)

    def __repr__(self):
        return f"{self.type}[{self.batch_id}|pur={self.purity}|T={self.T}]"

class Place:
    def __init__(self, name: str, capacity: int = None):
        self.name = name
        self.tokens = []   # list of ColouredToken
        self.capacity = capacity  # None means unlimited; otherwise number of tokens allowed

    def add_tokens(self, tokens):
        if isinstance(tokens, list):
            for t in tokens:
                if self.capacity is not None and len(self.tokens) >= self.capacity:
                    raise ValueError(f"Place {self.name} capacity exceeded")
                self.tokens.append(t)
        else:
            if self.capacity is not None and len(self.tokens) >= self.capacity:
                raise ValueError(f"Place {self.name} capacity exceeded")
            self.tokens.append(tokens)

    def remove_tokens(self, tokens):
        # tokens: list of token objects to remove (by identity)
        for t in tokens:
            self.tokens.remove(t)

    def count(self):
        return len(self.tokens)

    def find_tokens(self, condition_fn=None, limit=None):
        """
        Return a list of tokens satisfying condition_fn (or all if None).
        condition_fn(token) -> bool
        limit: maximum number of tokens to return
        """
        selected = []
        for t in self.tokens:
            if condition_fn is None or condition_fn(t):
                selected.append(t)
                if limit is not None and len(selected) >= limit:
                    break
        return selected

    def clear(self):
        self.tokens = []

    def __repr__(self):
        return f"Place({self.name}):{self.count()}"

class Transition:
    def __init__(self, name: str, inputs: dict, outputs: dict, guard=None, description: str = ""):
        """
        inputs: dict place_name -> weight (int)
        outputs: dict place_name -> weight (int) or token factory function
        guard: function(petri_net, selected_tokens_by_place) -> bool
               This guard runs after token selection (or can inspect places). If returns False, firing aborts.
        outputs may be a mapping place->callable(selected_tokens) returning list of tokens to add, OR
        a mapping place->int weight to produce default tokens (template-based).
        """
        self.name = name
        self.inputs = inputs or {}
        self.outputs = outputs or {}
        self.guard = guard
        self.description = description
        self.fired_count = 0

    def is_enabled(self, petri):
        # Check counts only (not guards)
        for pname, w in self.inputs.items():
            place = petri.places[pname]
            if place.count() < w:
                return False
        # optional: if guard wants to check static conditions (we let is_enabled be count-only)
        return True

    def select_tokens(self, petri):
        """
        Select tokens to consume on firing, according to inputs mapping.
        Selection policy: take first tokens that match optional per-place condition in guard.
        We return a dict: place_name -> list(tokens)
        """
        selected = {}
        for pname, w in self.inputs.items():
            place = petri.places[pname]
            # Default selection: any tokens (can be improved)
            sel = place.find_tokens(limit=w)
            if len(sel) < w:
                return None  # not enough tokens
            selected[pname] = sel
        return selected

    def fire(self, petri):
        if not self.is_enabled(petri):
            return False, "not enabled by counts"

        selected = self.select_tokens(petri)
        if selected is None:
            return False, "couldn't select tokens"

        # Evaluate guard if present. Provide shallow copy of selected tokens for guard checking.
        if self.guard:
            if not self.guard(petri, selected):
                return False, "guard blocked firing"

        # Remove tokens
        for pname, toks in selected.items():
            petri.places[pname].remove_tokens(toks)

        # Add outputs
        to_add = []
        for out_place_name, out_val in self.outputs.items():
            if callable(out_val):
                # outputs expressed as function producing token(s)
                new_tokens = out_val(selected, petri)
                if new_tokens:
                    petri.places[out_place_name].add_tokens(new_tokens if isinstance(new_tokens, list) else [new_tokens])
            else:
                # out_val is integer weight: produce default tokens based on context
                # create simple tokens by inspecting inputs where possible
                produced = []
                # try to infer type from transition name or inputs (simplified rule set)
                for i in range(int(out_val)):
                    # basic inference heuristics
                    if "NiCO4" in out_place_name or "NiCO4" in out_place_name.upper():
                        ttype = "NiCO4"
                        batch_id = f"B-{petri.next_batch_id()}"
                        token = ColouredToken(ttype, batch_id=batch_id, mass=1.0, T=25.0, purity=None)
                    elif "CO" in out_place_name.upper() or out_place_name.lower().startswith("p_co"):
                        ttype = "CO"
                        token = ColouredToken(ttype, batch_id=str(uuid.uuid4())[:8], mass=1.0)
                    elif "Ni" in out_place_name and "pure" in out_place_name:
                        ttype = "Ni_pure"
                        token = ColouredToken(ttype, batch_id=str(uuid.uuid4())[:8], mass=1.0, purity=0.99)
                    else:
                        # generic material token
                        token = ColouredToken("material", batch_id=str(uuid.uuid4())[:8], mass=1.0)
                    produced.append(token)
                petri.places[out_place_name].add_tokens(produced)

        self.fired_count += 1
        return True, selected

# -------------------------
# Petri Net engine
# -------------------------

class PetriNet:
    def __init__(self):
        self.places = {}
        self.transitions = {}
        self.stats = defaultdict(int)
        self.global_time = 0.0
        self._batch_counter = 0

    def add_place(self, place: Place):
        if place.name in self.places:
            raise ValueError("place exists")
        self.places[place.name] = place

    def add_transition(self, transition: Transition):
        if transition.name in self.transitions:
            raise ValueError("transition exists")
        self.transitions[transition.name] = transition

    def next_batch_id(self):
        self._batch_counter += 1
        return f"{self._batch_counter:04d}"

    def get_enabled_transitions(self):
        return [t for t in self.transitions.values() if t.is_enabled(self)]

    def step_fire(self, transition_name):
        tr = self.transitions[transition_name]
        ok, info = tr.fire(self)
        if ok:
            self.stats[f"fired::{transition_name}"] += 1
            return True, info
        else:
            return False, info

    def auto_run(self, steps=50, policy="random", verbose=False):
        """
        policy: 'random' -> pick random enabled transition
                'prioritise' -> use rule-based priority (T6, T10 higher)
        """
        for step in range(steps):
            enabled = [t for t in self.transitions.values() if t.is_enabled(self)]
            if not enabled:
                if verbose:
                    print(f"[time {self.global_time}] No enabled transitions. Halting at step {step}.")
                break
            chosen = None
            if policy == "random":
                chosen = random.choice(enabled)
            elif policy == "prioritise":
                # prioritize carbonylation (T6) and decomposition (T10) if enabled
                priority_names = ["T6", "T10", "T11", "T8", "T7"]
                for pname in priority_names:
                    for t in enabled:
                        if t.name == pname:
                            chosen = t
                            break
                    if chosen:
                        break
                if not chosen:
                    chosen = random.choice(enabled)
            else:
                chosen = random.choice(enabled)

            ok, info = chosen.fire(self)
            if ok:
                self.stats[f"fired::{chosen.name}"] += 1
                if verbose:
                    print(f"[step {step}] Fired {chosen.name}.")
            else:
                if verbose:
                    print(f"[step {step}] Failed attempt to fire {chosen.name}: {info}")
            # advance simple global clock tick
            self.global_time += 1.0

    def status_snapshot(self):
        snap = {pname: place.count() for pname, place in self.places.items()}
        return snap

    def print_status(self):
        print("=== Petri Net Status (grouped) ===")
        for name, place in self.places.items():
            counts = defaultdict(int)
            for token in place.tokens:
                counts[token.type] += 1
            summary = ", ".join(f"{t}:{c}" for t, c in counts.items())
            print(f"{name:<20}: {summary}")

# -------------------------
# Model construction helpers
# -------------------------

def build_mond_process():
    net = PetriNet()

    # Create places (match spec names)
    place_names = [
        "P_feed_ore", "P_crush", "P_leach", "P_concentrate", "P_impure_Ni",
        "P_CO_feed", "P_carbonylation", "P_NiCO4_gas", "P_condenser",
        "P_transfer_to_decomp", "P_decomposer", "P_pure_Ni", "P_CO_recycle",
        "P_scrubber", "P_offgas", "P_quality_check", "P_storage"
    ]
    # Example condenser capacity implemented using a capacity place 'P_condenser' with capacity param
    # (we maintain capacity checks in code by setting place.capacity)
    for name in place_names:
        if name == "P_condenser":
            net.add_place(Place(name, capacity=5))  # condenser can hold 5 tokens max
        else:
            net.add_place(Place(name))

    # initial marking
    # Add Ni ore tokens to P_feed_ore
    for i in range(10):
        t = ColouredToken("Ni_ore", batch_id=f"ORE{i+1:03d}", mass=1.0, purity=0.6)
        net.places["P_feed_ore"].add_tokens(t)

    # Add CO feed tokens to P_CO_feed
    for i in range(40):
        net.places["P_CO_feed"].add_tokens(ColouredToken("CO", batch_id=f"CO{i+1:03d}", mass=1.0))

    # Define guard helper functions where needed

    # T6 guard: carbonylation requires impure Ni token with acceptable purity and optionally temp between 50-60
    def guard_T6(petri, selected):
        # selected is dict: place -> [tokens]
        # check that at least one Ni ore token exists in selected P_impure_Ni
        toks = selected.get("P_impure_Ni", [])
        if not toks or len(toks) < 1:
            return False
        # Example check: require purity >= 0.5 (arbitrary threshold) for reaction
        tok = toks[0]
        if tok.purity is None:
            return True
        return tok.purity >= 0.5

    # T10 guard: decomposition requires heating; we emulate heating being always available for now
    def guard_T10(petri, selected):
        # ensure NiCO4 token(s) exist
        toks = selected.get("P_decomposer", [])
        return len(toks) >= 1

    # T12 guard/router: QC will be modelled probabilistically in output function

    # Output functions to create tokens with appropriate attributes
    def create_NiCO4(selected, petri):
        # We'll create one NiCO4 token per carbonylation firing
        inp = selected["P_impure_Ni"][0]
        batch_id = f"NC-{petri.next_batch_id()}"
        # NiCO4 inherits approximate mass from input and new temperature
        tok = ColouredToken("NiCO4", batch_id=batch_id, mass=inp.mass, T=25.0, purity=None)
        return tok

    def decompose_NiCO4_outputs(selected, petri):
        # For each NiCO4 consumed, produce 1 pure Ni and 4 CO recycle tokens
        produced = []
        inp = selected["P_decomposer"][0]
        # produce Ni_pure token (purity increases relative to feed)
        pure_batch = ColouredToken("Ni_pure", batch_id=f"NP-{petri.next_batch_id()}", mass=inp.mass, purity=0.99, T=25.0)
        produced.append(("P_pure_Ni", pure_batch))
        # produce 4 CO tokens in P_CO_recycle
        co_tokens = [ColouredToken("CO", batch_id=f"RCO-{petri.next_batch_id()}", mass=1.0) for _ in range(4)]
        # We will return token objects but transition.fire will place them as appropriate via outputs mapping
        # However outputs mapping expects tokens per output place individually, so we handle outside
        # Here we just return a dict-like structure; but to conform with our Transition interface, we'll
        # implement T10 outputs as callable generating tokens for both target places directly.
        return produced, co_tokens

    # For simplicity: implement T10 outputs via a custom callable mapping below.

    # Now create transitions exactly as spec (T1..T14)
    # T1 - Receive ore (external trigger)
    T1 = Transition("T1", inputs={}, outputs={"P_feed_ore": 1}, description="Receive ore (external).")
    # T2 - Crush / grind: feed_ore -> crush
    T2 = Transition("T2", inputs={"P_feed_ore": 1}, outputs={"P_crush": 1}, description="Crush/grind.")
    # T3 - Leach / concentrate: crush -> concentrate (optional)
    T3 = Transition("T3", inputs={"P_crush": 1}, outputs={"P_concentrate": 1}, description="Leach/concentrate.")
    # T4 - Prepare impure Ni feed: concentrate -> impure_Ni
    T4 = Transition("T4", inputs={"P_concentrate": 1}, outputs={"P_impure_Ni": 1}, description="Prepare impure Ni feed.")
    # T5 - Introduce CO (replenish): an external transition that adds tokens to CO feed.
    # Implemented as outputs to P_CO_feed with weight (we will call it manually to add tokens)
    T5 = Transition("T5", inputs={}, outputs={"P_CO_feed": 4}, description="Introduce/replenish CO (external).")
    # T6 - Carbonylation: impure_Ni + 4*CO -> NiCO4
    T6 = Transition(
        "T6",
        inputs={"P_impure_Ni": 1, "P_CO_feed": 4},
        outputs={"P_NiCO4_gas": create_NiCO4},
        guard=guard_T6,
        description="Carbonylation: Ni + CO -> Ni(CO)4"
    )
    # T7 - Transfer to condenser: NiCO4_gas -> condenser
    T7 = Transition("T7", inputs={"P_NiCO4_gas": 1}, outputs={"P_condenser": 1}, description="Transfer to condenser.")
    # T8 - Condense / collect Ni(CO)4: condenser -> transfer_to_decomp
    # Must check condenser capacity: implemented via Place capacity; we simply move tokens on firing
    T8 = Transition("T8", inputs={"P_condenser": 1}, outputs={"P_transfer_to_decomp": 1}, description="Condense/collect Ni(CO)4.")
    # T9 - Transfer to decomposer: transfer_to_decomp -> decomposer
    T9 = Transition("T9", inputs={"P_transfer_to_decomp": 1}, outputs={"P_decomposer": 1}, description="Transfer to decomposer.")
    # T10 - Decomposition: NiCO4 -> Ni_pure + 4 CO_recycle
    def T10_output_callable(selected, petri):
        # selected has P_decomposer: [NiCO4 token]
        inp = selected["P_decomposer"][0]
        # produce pure Ni
        ni_pure = ColouredToken("Ni_pure", batch_id=f"NP-{petri.next_batch_id()}", mass=inp.mass, purity=0.99, T=25.0)
        # produce 4 CO tokens to go to P_CO_recycle
        co_out = [ColouredToken("CO", batch_id=f"RCO-{petri.next_batch_id()}", mass=1.0) for _ in range(4)]
        # Place Ni_pure into P_pure_Ni and CO tokens into P_CO_recycle
        # Transition outputs mapping functions must return single token or list; we return list for each place
        petri.places["P_pure_Ni"].add_tokens(ni_pure)
        petri.places["P_CO_recycle"].add_tokens(co_out)
        return None  # we've already handled adding to places
    T10 = Transition("T10", inputs={"P_decomposer": 1}, outputs={"P_pure_Ni": T10_output_callable}, guard=guard_T10, description="Decomposition: NiCO4 -> Ni + CO")
    # T11 - CO recycle to feed: P_CO_recycle -> P_CO_feed
    T11 = Transition("T11", inputs={"P_CO_recycle": 1}, outputs={"P_CO_feed": 1}, description="CO recycle to feed.")
    # T12 - Quality check: P_pure_Ni -> P_storage (pass) OR P_scrubber (fail)
    # We'll implement two transitions: T12_pass and T12_fail for deterministic firing; but here we implement T12 as a probabilistic router.
    def T12_callable(selected, petri):
        tok = selected["P_pure_Ni"][0]
        # simulate QC: pass with prob based on purity (cap between 0 and 1)
        pass_prob = tok.purity if tok.purity is not None else 0.95
        if random.random() <= pass_prob:
            petri.places["P_storage"].add_tokens(tok.copy())
            # increase stat
            petri.stats["qc_passed"] += 1
        else:
            petri.places["P_scrubber"].add_tokens(tok.copy())
            petri.stats["qc_failed"] += 1
        # No need to return because we've added to places. The consumed token is already removed by transition.fire
        return None
    T12 = Transition("T12", inputs={"P_pure_Ni": 1}, outputs={"P_storage": T12_callable}, description="Quality check (probabilistic).")

    # T13 - Scrap / Waste handling: P_scrubber -> P_offgas
    T13 = Transition("T13", inputs={"P_scrubber": 1}, outputs={"P_offgas": 1}, description="Scrap/waste handling.")
    # T14 - Emergency vent / safety: triggered from P_NiCO4_gas or P_condenser overload -> P_scrubber or P_offgas
    # Implement as one transition that consumes a gaseous token and sends it to offgas
    T14 = Transition("T14", inputs={"P_NiCO4_gas": 1}, outputs={"P_scrubber": 1}, description="Emergency vent - route to scrubber.")

    # Add transitions to net
    for t in [T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14]:
        net.add_transition(t)

    return net

# -------------------------
# BFS sequence finder (simple)
# -------------------------
def find_sequence_bfs(net: PetriNet, goal_check_fn, max_depth=8):
    """
    Try to find a firing sequence of transitions (by name) up to max_depth that reaches a state satisfying goal_check_fn(snapshot).
    This is an exponential search in worst case; used for small toy examples.
    """
    initial_snapshot = deepcopy(net)
    queue = deque()
    queue.append((initial_snapshot, []))  # (net_copy, sequence)
    visited = 0
    while queue:
        current_net, seq = queue.popleft()
        visited += 1
        if goal_check_fn(current_net.status_snapshot()):
            return seq
        if len(seq) >= max_depth:
            continue
        # get enabled transitions in current_net
        enabled = [t for t in current_net.transitions.values() if t.is_enabled(current_net)]
        for t in enabled:
            # simulate firing on a deep copy
            net_copy = deepcopy(current_net)
            ok, info = net_copy.transitions[t.name].fire(net_copy)
            # if fired (should be), push new state
            if ok:
                queue.append((net_copy, seq + [t.name]))
    return None

# -------------------------
# Demo / main
# -------------------------

def main():
    print("Building Mond Process Petri Net...")
    net = build_mond_process()
    print("Initial status:")
    net.print_status()

    # Example: run a few manual steps to process feed: we'll try to run T2..T4 to convert feed ore to impure_Ni, then trigger carbonylation (T6) repeatedly
    # We will run an automatic simulation with a simple policy for a number of steps
    print("Running automatic simulation (policy: prioritise T6/T10) ...")
    net.auto_run(steps=200, policy="prioritise", verbose=False)

    print("\nAfter auto-run status:")
    net.print_status()

    # Run QC on any P_pure_Ni tokens by firing T12 repeatedly
    while net.places["P_pure_Ni"].count() > 0:
        ok, info = net.step_fire("T12")
        if not ok:
            # if guard blocked for some reason, break
            break

    print("After QC routing:")
    net.print_status()

    # Print summary stats
    print("=== Summary stats ===")
    for k, v in net.stats.items():
        print(f"{k}: {v}")
    print("=====================")

    # Example BFS goal: find sequence to produce at least one token in P_storage starting from initial small net
    # Use a small shallow net to test BFS. (Be careful: BFS with our full net can blow up.)
    print("\nAttempting small BFS from current net snapshot to find a sequence that yields P_storage >=1 ... (max depth 6)")
    def goal_fn(snapshot):
        return snapshot.get("P_storage", 0) >= 1
    seq = find_sequence_bfs(net, goal_fn, max_depth=6)
    if seq:
        print("Found sequence:", seq)
    else:
        print("No sequence found within depth.")

if __name__ == "__main__":
    main()
