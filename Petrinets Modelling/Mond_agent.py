# mond_agent.py
# Agent wrapper for the Mond Process Petri Net

import random
from Mond_process import build_mond_process, PetriNet

# -------------------------
# Environment wrapper
# -------------------------
class MondEnv:
    def __init__(self):
        self.net = None
        self.reset()

    def reset(self):
        """Reset to initial state"""
        self.net = build_mond_process()
        return self.get_state()

    def get_state(self):
        """Observation = token counts in key places"""
        return {name: place.count() for name, place in self.net.places.items()}

    def get_actions(self):
        """Return list of enabled transition names"""
        return [t.name for t in self.net.get_enabled_transitions()]

    def step(self, action_name):
        """Agent fires a transition"""
        success, info = self.net.step_fire(action_name)
        obs = self.get_state()

        # Simple reward function
        reward = 0
        reward += obs.get("P_storage", 0) * 10       # reward for pure Ni
        reward -= obs.get("P_scrubber", 0) * 5       # penalty for waste
        reward -= obs.get("P_offgas", 0) * 2         # small penalty for offgas

        return obs, reward, success

# -------------------------
# Rule-based Agent
# -------------------------
class RuleAgent:
    def choose_action(self, env):
        actions = env.get_actions()
        if not actions:
            return None
        # prioritise decomposition and carbonylation
        for t in ["T10", "T6"]:
            if t in actions:
                return t
        return random.choice(actions)

# -------------------------
# Run Agent Simulation
# -------------------------
def run_agent_simulation(steps=50, verbose=True):
    env = MondEnv()
    agent = RuleAgent()
    state = env.reset()
    total_reward = 0

    for step in range(steps):
        action = agent.choose_action(env)
        if action is None:
            if verbose:
                print("No enabled transitions. Ending simulation.")
            break
        obs, reward, success = env.step(action)
        total_reward += reward
        if verbose:
            print(f"Step {step+1}: Fired {action}, Reward={reward}, Total={total_reward}")

    if verbose:
        print("\nFinal token counts:", state)
        print("Simulation finished. Total reward:", total_reward)

# -------------------------
# Run if script is called directly
# -------------------------
if __name__ == "__main__":
    run_agent_simulation()
