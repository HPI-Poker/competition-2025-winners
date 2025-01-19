from config import SUMMARY_PATH, STARTING_STACK, NUM_ROUNDS
from collections import namedtuple
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HandDelta = namedtuple('HandDelta', ['round_num', 'chip_delta'])

# VPIP: Voluntarily Put Money in Pot: measures how often one voluntarily pays money into a hand before seeing the flop. Paying the big blind, the small blind, or the ante is not considered voluntary.
# PFR : Preflop Raise
class PlayerSummary:
    def __init__(self, player1_name):
        self.player1_name = player1_name
        self.num_won_at_showdown = 0
        self.num_vpip_opportunities = 0
        self.num_vpip = 0
        self.num_pfr_opportunities = 0 # not all vpip opportunities are pfr opportunities (e.g. opponent is all-in)
        self.num_pfr = 0
        self.num_illegal_actions = 0
        self.num_timeouts = 0

    def get_pfr(self):
        if self.num_vpip_opportunities == 0:
            return 1.0
        return round(self.num_pfr / self.num_vpip_opportunities, 3)

    def get_vpip(self):
        if self.num_vpip_opportunities == 0:
            return 1.0
        return round(self.num_vpip / self.num_vpip_opportunities, 3)

    def log(self):
        return {
            'name': self.player1_name,
            'VPIP': self.get_vpip(),
            'PFR': self.get_pfr(),
            'illegal actions': self.num_illegal_actions,
            'timeouts': self.num_timeouts,
        }

class GameSummary:
    def __init__(self, players, match_id):
        self.match_id = match_id
        self.players = players
        self.discretized_bankrolls = [(0, [0, 0])]
        self.hand_deltas = []
        self.player_summaries = [PlayerSummary(players[0]), PlayerSummary(players[1])]
        self.num_chops = 0
        self.logs = []

    def add_bankrolls(self, round_num, name_to_bankrolls):
        if (name_to_bankrolls.keys() != set(self.players)):
            raise Exception(f"Unknown player names: {name_to_bankrolls.keys()}")
        bankrolls = [name_to_bankrolls[self.players[0]], name_to_bankrolls[self.players[1]]]
        self.discretized_bankrolls.append((round_num, bankrolls))

    def add_pfr_opportunity(self, player_name):
        self.player_summaries[self._name_to_player_id(player_name)].num_pfr_opportunities += 1

    def add_pfr(self, player_name):
        self.player_summaries[self._name_to_player_id(player_name)].num_pfr += 1

    def add_vpip_opportunity(self, player_name):
        self.player_summaries[self._name_to_player_id(player_name)].num_vpip_opportunities += 1
    
    def add_vpip(self, player_name):
        self.player_summaries[self._name_to_player_id(player_name)].num_vpip += 1

    def add_round(self, round_num, name_to_delta): # chip counts order needs to be self.players'
        if (name_to_delta.keys() != set(self.players)):
            raise Exception(f"Unknown player names: {name_to_delta.keys()}")
        d = HandDelta(round_num, [name_to_delta[self.players[0]], name_to_delta[self.players[1]]])
        self.hand_deltas.append(d)

    def get_top_hands(self, no_of_hands) -> list:
        self.hand_deltas.sort(key=lambda x: x[1], reverse=True)
        return self.hand_deltas[:no_of_hands]
    
    def add_illegal_action(self, player_name):
        self.player_summaries[self._name_to_player_id(player_name)].num_illegal_actions += 1

    def add_timeout(self, player_name):
        self.player_summaries[self._name_to_player_id(player_name)].num_timeouts += 1

    def set_logs(self, logs):
        self.logs = logs

    def write_summary(self):
        name =  'SUM_' + self.match_id + '_' + self.players[0] + '_vs_' + self.players[1] + '.json'
        summary_path = os.path.join(BASE_DIR, SUMMARY_PATH)
        summary_file = os.path.join(summary_path, name)

        print("Writing game summary to " + summary_file)

        bankrolls = self.discretized_bankrolls[-1][1]
        self.log = {
            'Game Summary': self.players[0] + ' vs ' + self.players[1],
            'Score': str(bankrolls[0]) + ' vs ' + str(bankrolls[1]),
            'Tie': bankrolls[0] == bankrolls[1],
            'Winner': None if bankrolls[0] == bankrolls[1] else (self.players[0] if bankrolls[0] > bankrolls[1] else self.players[1]),
            'Starting stack': STARTING_STACK,
            'Number of rounds': NUM_ROUNDS,
            'Number of chop': self.num_chops,
            'Player stats': [p.log() for p in self.player_summaries],
            'Discretized bankroll counts': self._log_discretized_bankrolls(),
            'Top hands': self._log_top_hands(5),
            'Logs': self.logs,
        }
        os.makedirs(summary_path, exist_ok=True)
        with open(summary_file, 'w') as json_file:
            json.dump(self.log, json_file, indent=2)

    def _name_to_player_id(self, player_name):
        if player_name == self.players[0]:
            return 0
        elif player_name == self.players[1]:
            return 1
        else:
            raise Exception(f"Unknown player name: {player_name}")
        
    def _log_discretized_bankrolls(self):
        log = []
        for round_num, bankrolls in self.discretized_bankrolls:
            log.append({
                'Round number': round_num,
                'Player_1_bankroll': bankrolls[0],
                'Player_2_bankroll': bankrolls[1]
            })
        return log

    def _log_top_hands(self, no_of_hands):
        log = []
        hands = self.get_top_hands(no_of_hands)
        for hand in hands:
            log.append({
                'Round number': hand.round_num,
                'Chip delta': hand.chip_delta
            })
        return log
