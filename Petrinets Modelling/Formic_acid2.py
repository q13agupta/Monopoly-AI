import numpy as np
import random
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt

# -------------------------
# Coloured Petri Net
# -------------------------
class ColouredPetriNet:
    def __init__(self):
        self.places = {
            'Feed': [
                {'species': 'CO2', 'amount': 98000},
                {'species': 'H2', 'amount': 98000},
                {'species': 'N2', 'amount': 4000},
                {'species': 'Am', 'amount': 88200}
            ],
            'R1': [],
            'Flash_Liquid': [],
            'Flash_Vapor': [],
            'Recycle': [],
            'Purge': [],
            'R2': [],
            'Product_HCOOH': [],
            'Am_Recycle': []
        }

    def print_marking(self):
        print("Current marking:")
        for place, tokens in self.places.items():
            summary = {}
            for t in tokens:
                summary[t['species']] = summary.get(t['species'], 0) + t['amount']
            print(f"{place}: {summary}")

    def get_amount(self, place, species):
        return sum(t['amount'] for t in self.places[place] if t['species']==species)

    def remove_species(self, place, species, amount):
        tokens = self.places[place]
        removed = 0
        new_tokens = []
        for t in tokens:
            if t['species'] == species and removed < amount:
                take = min(t['amount'], amount - removed)
                removed += take
                if t['amount'] > take:
                    new_tokens.append({'species': species, 'amount': t['amount'] - take})
            else:
                new_tokens.append(t)
        self.places[place] = new_tokens

    def add_token(self, place, species, amount):
        for t in self.places[place]:
            if t['species'] == species:
                t['amount'] += amount
                return
        self.places[place].append({'species': species, 'amount': amount})

    # -------------------------
    # Transitions
    # -------------------------
    def T_R1_rxn1(self):
        co2_amt = self.get_amount('Feed','CO2')
        h2_amt = self.get_amount('Feed','H2')
        conv = 0.9
        react_amt = min(co2_amt, h2_amt) * conv
        if react_amt > 0:
            self.remove_species('Feed','CO2', react_amt)
            self.remove_species('Feed','H2', react_amt)
            self.add_token('R1','HCOOH', react_amt)

    def T_R1_rxn2(self):
        hcooh_amt = self.get_amount('R1','HCOOH')
        am_amt = self.get_amount('Feed','Am')
        conv = 0.9
        react_amt = min(hcooh_amt, am_amt) * conv
        if react_amt > 0:
            self.remove_species('R1','HCOOH', react_amt)
            self.remove_species('Feed','Am', react_amt)
            self.add_token('R1','HCOOH·Am', react_amt)

    def T_R1_to_flash(self):
        for t in list(self.places['R1']):
            self.add_token('Flash_Liquid' if t['species'] in ['HCOOH','HCOOH·Am','Am'] else 'Flash_Vapor', t['species'], t['amount'])
        self.places['R1'] = []

    def T_Flash_split(self):
        new_flash_liquid = []
        new_flash_vapor = []
        for t in list(self.places['Flash_Liquid']):
            if t['species']=='HCOOH':
                liq_amt = int(0.95 * t['amount'])
                vap_amt = t['amount'] - liq_amt
                if liq_amt>0: new_flash_liquid.append({'species':'HCOOH','amount':liq_amt})
                if vap_amt>0: new_flash_vapor.append({'species':'HCOOH','amount':vap_amt})
            else:
                new_flash_liquid.append(t)
        self.places['Flash_Liquid'] = new_flash_liquid
        self.places['Flash_Vapor'].extend(new_flash_vapor)

    def T_Vapor_split(self):
        new_recycle = []
        for t in list(self.places['Flash_Vapor']):
            rec_amt = int(0.9 * t['amount'])
            purge_amt = t['amount'] - rec_amt
            if rec_amt>0: new_recycle.append({'species': t['species'], 'amount': rec_amt})
            if purge_amt>0: self.add_token('Purge', t['species'], purge_amt)
        self.places['Recycle'].extend(new_recycle)
        self.places['Flash_Vapor'] = []

    def T_Recycle_to_feed(self):
        for t in list(self.places['Recycle']):
            if t['species'] in ['CO2','H2','N2','HCOOH']:
                self.add_token('Feed', t['species'], t['amount'])
        self.places['Recycle'] = []

    def T_R2_crack(self):
        for t in list(self.places['Flash_Liquid']):
            self.add_token('R2', t['species'], t['amount'])
        self.places['Flash_Liquid'] = []

        complex_amt = self.get_amount('R2','HCOOH·Am')
        if complex_amt>0:
            self.remove_species('R2','HCOOH·Am', complex_amt)
            self.add_token('R2','HCOOH', complex_amt)
            self.add_token('R2','Am', complex_amt)

    def T_Final_separation(self):
        for t in list(self.places['R2']):
            if t['species']=='HCOOH':
                self.add_token('Product_HCOOH', t['species'], t['amount'])
            elif t['species']=='Am':
                self.add_token('Am_Recycle', t['species'], t['amount'])
        self.places['R2'] = []

    def T_Return_Am(self):
        for t in list(self.places['Am_Recycle']):
            self.add_token('Feed', t['species'], t['amount'])
        self.places['Am_Recycle'] = []

# -------------------------
# DQN Agent
# -------------------------
class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN,self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim,128),
            nn.ReLU(),
            nn.Linear(128,128),
            nn.ReLU(),
            nn.Linear(128,output_dim)
        )
    def forward(self,x):
        return self.fc(x)

class DQNAgent:
    def __init__(self, net, lr=1e-3, gamma=0.9, epsilon=0.2):
        self.net = net
        self.epsilon = epsilon
        self.gamma = gamma
        self.model = DQN(input_dim=12, output_dim=9)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        self.loss_fn = nn.MSELoss()
        self.actions = [
            net.T_R1_rxn1,
            net.T_R1_rxn2,
            net.T_R1_to_flash,
            net.T_Flash_split,
            net.T_Vapor_split,
            net.T_Recycle_to_feed,
            net.T_R2_crack,
            net.T_Final_separation,
            net.T_Return_Am
        ]

    def get_state_vector(self):
        places = ['Feed','R1','Flash_Liquid','Flash_Vapor','Recycle','R2']
        species = ['CO2','H2','N2','HCOOH','Am','HCOOH·Am']
        state = []
        for place in places:
            for sp in species:
                state.append(self.net.get_amount(place, sp))
        return torch.tensor(state,dtype=torch.float32)

    def choose_action(self):
        state = self.get_state_vector()
        if random.random() < self.epsilon:
            return random.randint(0,len(self.actions)-1)
        else:
            with torch.no_grad():
                qvals = self.model(state)
            return int(torch.argmax(qvals))

    def train_step(self, state, action, reward, next_state):
        self.optimizer.zero_grad()
        qvals = self.model(state)
        next_qvals = self.model(next_state)
        target = qvals.clone().detach()
        target[action] = reward + self.gamma*torch.max(next_qvals)
        loss = self.loss_fn(qvals, target)
        loss.backward()
        self.optimizer.step()

# -------------------------
# Training Loop
# -------------------------
def train(agent, episodes=200):
    rewards = []
    for ep in range(episodes):
        agent.net.__init__() # reset Petri Net
        total_reward = 0
        state = agent.get_state_vector()
        for step in range(20):
            action_idx = agent.choose_action()
            action_func = agent.actions[action_idx]
            prev_product = agent.net.get_amount('Product_HCOOH','HCOOH')
            action_func()
            delta = agent.net.get_amount('Product_HCOOH','HCOOH') - prev_product
            purge = agent.net.get_amount('Purge','CO2') + agent.net.get_amount('Purge','H2')
            reward = delta - 0.1*purge
            next_state = agent.get_state_vector()
            agent.train_step(state, action_idx, reward, next_state)
            state = next_state
            total_reward += reward
        rewards.append(total_reward)
        if ep % 20 == 0:
            print(f"Episode {ep}, total reward: {total_reward}, Product HCOOH: {agent.net.get_amount('Product_HCOOH','HCOOH')}")
    return rewards

# -------------------------
# Run Training and Plot
# -------------------------
if __name__ == "__main__":
    cpn_net = ColouredPetriNet()
    agent = DQNAgent(cpn_net)
    rewards = train(agent, episodes=200)

    plt.plot(rewards)
    plt.xlabel('Episode')
    plt.ylabel('Total Reward')
    plt.title('DQN Training Rewards over Episodes')
    plt.show()

    print("\nFinal Petri Net Marking after last episode:")
    cpn_net.print_marking()
