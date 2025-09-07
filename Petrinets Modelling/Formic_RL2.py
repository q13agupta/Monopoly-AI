import numpy as np
import random

# Q-Learning Agent for Petri Net
class QLearningAgent:
    def __init__(self, net, bins=10, alpha=0.1, gamma=0.9, epsilon=0.2):
        self.net = net
        self.alpha = alpha   # learning rate
        self.gamma = gamma   # discount factor
        self.epsilon = epsilon # exploration probability
        self.bins = bins
        # Actions: transitions 0-8
        self.actions = [
            net.T_R1_rxn1,
            net.T_R1_rxn2,
            net.T_R1_collect,
            net.T_Flash_split,
            net.T_Vapor_split,
            net.T_Recycle_To_R1,
            net.T_R2_crack,
            net.T_Final_Separation,
            net.T_Return_Am
        ]
        self.q_table = {}  # key: state tuple, value: action values

    # Discretize state into bins
    def discretize_state(self):
        places = ['P_CO2_feed', 'P_H2_feed', 'P_Flash_In', 'P_Liquid_Buffer', 'P_Vapor_Buffer', 'P_Product_HCOOH']
        state = []
        for p in places:
            val = self.net.places[p]
            max_val = max(1, val)  # prevent zero division
            bin_val = int(val / max_val * (self.bins - 1))
            state.append(bin_val)
        return tuple(state)

    # Choose action using epsilon-greedy
    def choose_action(self, state):
        if state not in self.q_table:
            self.q_table[state] = np.zeros(len(self.actions))
        if random.random() < self.epsilon:
            return random.randint(0, len(self.actions)-1)
        else:
            return int(np.argmax(self.q_table[state]))

    # Update Q-table
    def update_q(self, state, action, reward, next_state):
        if next_state not in self.q_table:
            self.q_table[next_state] = np.zeros(len(self.actions))
        old_value = self.q_table[state][action]
        next_max = np.max(self.q_table[next_state])
        new_value = old_value + self.alpha * (reward + self.gamma * next_max - old_value)
        self.q_table[state][action] = new_value

    # Run one episode
    def run_episode(self, max_steps=20):
        self.net.__init__()  # reset Petri Net
        total_reward = 0
        for _ in range(max_steps):
            state = self.discretize_state()
            action_idx = self.choose_action(state)
            action_func = self.actions[action_idx]

            # Snapshot product HCOOH before action
            prev_product = self.net.places['P_Product_HCOOH']

            # Fire transition
            action_func()

            # Reward = increase in product - 0.1 * purge
            delta_product = self.net.places['P_Product_HCOOH'] - prev_product
            reward = delta_product - 0.1 * self.net.places['P_Purge']

            next_state = self.discretize_state()
            self.update_q(state, action_idx, reward, next_state)

            total_reward += reward

        return total_reward
