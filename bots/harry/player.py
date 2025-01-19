from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot
from builtins import int

import eval7
import random
import pandas as pd
import os
import itertools

NUM_HOLE_CARD_COMBINATIONS = 169
preflop_hand_open_raise_pct = 20 # % of hands the cats wants to open raise preflop with
preflop_limp_pct = 66 # % of hands the cat wants to play preflop

open_raise_range = NUM_HOLE_CARD_COMBINATIONS * preflop_hand_open_raise_pct // 100
limp_range = NUM_HOLE_CARD_COMBINATIONS * preflop_limp_pct // 100 # limping refers to emerely calling the big blind
open_raise_size = 2.5

def check_call_action(round_state):
    if CheckAction in round_state.legal_actions():
        return CheckAction()
    return CallAction()

def check_fold_action(round_state):
    if CheckAction in round_state.legal_actions():
        return CheckAction()
    return FoldAction()

def hole_list_to_key(hole):
    card_1 = hole[0]
    card_2 = hole[1]

    rank_1, suit_1 = card_1[0], card_1[1] 
    rank_2, suit_2 = card_2[0], card_2[1]

    numeric_1, numeric_2 = rank_to_numeric(rank_1), rank_to_numeric(rank_2) 

    suited = suit_1 == suit_2 
    suit_string = 's' if suited else 'o'

    if numeric_1 >= numeric_2:
        return rank_1 + rank_2 + suit_string
    else:
        return rank_2 + rank_1 + suit_string

def rank_to_numeric(rank):
    # return int(rank) if rank.isnumeric() else {'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}[rank]
    
    if rank.isnumeric(): #2-9, we can just use the int version of this string
        return int(rank)
    elif rank == 'T': #10 is T, so we need to specify it here
        return 10
    elif rank == 'J': #Face cards for the rest of them
        return 11
    elif rank == 'Q':
        return 12
    elif rank == 'K':
        return 13
    else:
        return 14

def check_fold(round_state):
    if CheckAction in round_state.legal_actions():
        return CheckAction()
    return FoldAction()

def is_straight(ranks):
    for i in range(9):
        if ranks[i] >= 1 and ranks[i+1] >= 1 and ranks[i+2] >= 1 and ranks[i+3] >= 1 and ranks[i+4] >= 1:
            return True
    if ranks[0] >= 1 and ranks[1] >= 1 and ranks[2] >= 1 and ranks[3] >= 1 and ranks[12] >= 1:
        return True
    return False

def board_heaviness(board):
    """
    Assess the 'heaviness' of a board using metrics like flush draws, straight draws, and pairing.
    :param board: List of 3 eval7.Card objects (the flop)
    :return: A score indicating the heaviness of the board
    """
    suits = [card[1] for card in board]
    ranks = [card[0] for card in board]
    
    # Check for flush draw potential
    suit_counts = {suit: suits.count(suit) for suit in set(suits)}
    flush_draw = max(suit_counts.values()) >= 2  # At least 2 cards of the same suit
    
    # Check for straight draw potential
    rank_values = sorted([eval7.Card(rank + 's').rank for rank in ranks])  # Get rank values
    straight_draw = (
        (rank_values[2] - rank_values[0] <= 4) or  # Close ranks
        (14 in rank_values and 2 in rank_values and 3 in rank_values)  # Wrap-around straight potential
    )
    
    # Check for paired boards
    paired = len(set(ranks)) < len(ranks)  # True if there are duplicate ranks
    
    # Assign weights to each feature
    heaviness_score = (
        (3 if flush_draw else 0) +
        (3 if straight_draw else 0) +
        (2 if paired else 0)
    )
    
    return heaviness_score

def classify_boards(flop):
    """
    Classify a flop as heavy or weak based on its heaviness score.
    """
    heaviness = board_heaviness(flop)
    return "Heavy" if heaviness >= 5 else "Weak"

def can_win_by_folding(game_state, round_state, active) -> bool:
    remaining_rounds = NUM_ROUNDS - game_state.round_num
    big_blind = bool(active)
    my_bankroll = game_state.bankroll
    
    num_of_remaining_big_blind_rounds = remaining_rounds // 2
    if remaining_rounds % 2 == 0 and big_blind:
        num_of_remaining_big_blind_rounds -= 1
    num_of_remaining_small_blind_rounds = remaining_rounds - num_of_remaining_big_blind_rounds
   
    cost_of_folding = num_of_remaining_big_blind_rounds * BIG_BLIND + num_of_remaining_small_blind_rounds * SMALL_BLIND
    
    return cost_of_folding < my_bankroll

class Player(Bot):
    '''
    Scaredy Cat is cautious from their old multiway poker days, and tries to avoid big pots unless they have a strong hand.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.

        Arguments:
        Nothing.

        Returns:
        Nothing.
        '''
        script_dir = os.path.dirname(__file__)
        calculated_df = pd.read_csv(os.path.join(script_dir, 'preflop_lookup.csv')) # do not sort by rank
        hole_cards = calculated_df.Holes
        self.preflop_strength = dict(zip(hole_cards, calculated_df.WinPct))
        self.preflop_ranks = dict(zip(hole_cards, calculated_df.Ranks))
        
        self.parameters = {
            "p_bad_hand_bluff": 0.3,
            "p_call_or_raise_bluff": 0.8,
            "p_reraise_bluff": 0.3,
            "medium_hand_strength_offset": 0.1,
            "p_premium_hand_trap": 0.5,
            "p_all_in_bet": 0.05,
    
        }
        self.all_combinations = list(itertools.combinations(eval7.Deck(), 2))
        self.all_combinations_with_weight = [([card[0], card[1]], 1.0) for card in self.all_combinations]
        self.is_bluffing = False

    
    def handle_new_round(self, game_state, round_state, active):
        my_cards = round_state.hands[active]  # your cards
        
        self.card_ranks = [0] * 13
        self.card_suits = [0] * 4
        self.my_cards = [eval7.Card(card) for card in my_cards]
        self.strength = self.preflop_strength[hole_list_to_key(my_cards)]
        
        self.previous_street = -1

            
    def handle_new_street(self, game_state, round_state, active):
        deck = [eval7.Card(card) for card in round_state.deck]
        self.previous_street = round_state.street
        
        if round_state.street == 0:
            for card in self.my_cards:
                self.card_ranks[card.rank] += 1
                self.card_suits[card.suit] += 1
                
            for card in deck:
                self.card_ranks[card.rank] += 1
                self.card_suits[card.suit] += 1
        
        else:
            self.card_ranks[deck[-1].rank] += 1
            self.card_suits[deck[-1].suit] += 1
        
        my_cards = [eval7.Card(x) for x in round_state.hands[active]]
        street = round_state.street
        board_cards = [eval7.Card(x) for x in round_state.deck[:street]]
        self.strength = self.calculate_hand_strength(my_cards, board_cards)
                    
    def handle_round_over(self, game_state, terminal_state, active):
        self.is_bluffing = False
    
    def open_bet (self, min_raise: int, max_raise: int) -> int: 
        if random.random() < self.parameters["p_all_in_bet"]:
            return max_raise       
        bet = random.uniform(2,2.5)
        return min(max_raise, int(bet * min_raise))
    
    def three_bet(self,  min_raise: int, max_raise: int) -> int:
        bet_modifier = random.uniform(3.0, 4.0)
        return min(max_raise, int(bet_modifier * min_raise))

    def all_in_bet(self, min_raise: int, max_raise: int) -> int:
        return max_raise
    

    def call_or_raise_bluff_preflop(self, game_state, round_state, active):
        my_pip = round_state.pips[active]  # the number of chips you have contributed to the pot this round of betting
        opp_pip = round_state.pips[1-active]  # th
        continue_cost = opp_pip - my_pip  # the number of chips needed to stay in the pot
        my_stack = round_state.stacks[active]  # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active]  # the number of ch
        my_contribution = STARTING_STACK - my_stack  # the number of chips you have contributed to the pot
        opp_contribution = STARTING_STACK - opp_stack  # the number of chips your opponent has contributed to the pot
        pot_total = my_contribution + opp_contribution
        pot_odds = continue_cost / (pot_total + continue_cost)
        min_raise, max_raise = round_state.raise_bounds()

        if continue_cost > 0:
            if pot_odds < self.strength or random.random() < self.parameters["p_call_or_raise_bluff"]:
                if  random.random() < self.parameters["p_reraise_bluff"]:

                    return self.legal_raise(self.three_bet(min_raise, max_raise), round_state, active)
                return check_call_action(round_state=round_state)
            else:
                return check_fold(round_state)
        else:
            return self.legal_raise(self.open_bet(min_raise, max_raise), round_state, active)

    def p_opp_is_bluffing(self, game_state) -> float:
        return 0.05
    
    def preflop_action(self, game_state, round_state, active):
        legal_actions = round_state.legal_actions()  # the actions you are allowed to take
        my_cards = round_state.hands[active]  # your cards
        my_pip = round_state.pips[active]  # the number of chips you have contributed to the pot this round of betting
        opp_pip = round_state.pips[1-active]  # the number of chips your opponent has contributed to the pot this round of betting
        my_stack = round_state.stacks[active]  # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active]  # the number of chips your opponent has remaining
        continue_cost = opp_pip - my_pip  # the number of chips needed to stay in the pot
        my_contribution = STARTING_STACK - my_stack  # the number of chips you have contributed to the pot
        opp_contribution = STARTING_STACK - opp_stack  # the number of chips your opponent has contributed to the pot
        pot_total = my_contribution + opp_contribution
        pot_odds = continue_cost / (pot_total + continue_cost)

        card_rank = self.preflop_ranks[hole_list_to_key(my_cards)]
        card_rank = int(card_rank)
        
        randomized_limp_range = limp_range + random.randint(-5, 5)
        randomized_open_raise_range = open_raise_range + random.randint(-2, 2)

        is_bad = card_rank > randomized_limp_range
        is_medium = randomized_limp_range >= card_rank and card_rank > randomized_open_raise_range
        

        min_raise, max_raise = round_state.raise_bounds()
        if is_bad:
            if random.random() < self.parameters["p_bad_hand_bluff"] and continue_cost <= 1:
                self.is_bluffing = True
                return self.legal_raise(self.open_bet( min_raise, max_raise), round_state, active)
            else:
                return check_fold(round_state)
        elif is_medium:
            p_is_bluffing =  self.p_opp_is_bluffing(game_state)
            if p_is_bluffing > 0.5 and random.random() < p_is_bluffing:
                return self.call_or_raise_bluff_preflop(game_state, round_state, active)
            else:
                if self.strength > pot_odds + self.parameters["medium_hand_strength_offset"] and continue_cost == 1:
                    return check_call_action(round_state)
                else:
                    return check_fold(round_state)
        else:
            if random.random() < self.parameters["p_premium_hand_trap"]:
                return check_call_action(round_state)  # Slow-play to keep opponent in the pot
            else:
                if RaiseAction in legal_actions:
                    if continue_cost <= 1:
                        return self.legal_raise(self.open_bet(min_raise, max_raise), round_state, active)
                    else:
                        return self.legal_raise(self.three_bet(min_raise, max_raise), round_state, active)
                else:
                    return check_call_action(round_state)

    def calculate_hand_strength(self, hand_cards, community_cards) -> float:
        used_cards = set(hand_cards + community_cards)
        all_possible_other_hand_cards = [self.all_combinations_with_weight[i] for i in range(len(self.all_combinations)) if self.all_combinations[i][0] not in used_cards or self.all_combinations[i][1] not in used_cards]
        return eval7.py_hand_vs_range_monte_carlo(hand_cards, all_possible_other_hand_cards, community_cards, 1000)

    def scared_eval_hand(self):
        has_pair = False # does not include board pairs
        has_flush_draw = False # ignores board flush draws
        has_straight_draw = False
        num_overcards = 0
        for card in self.my_cards:
            if self.card_ranks[card.rank] >= 2:
                has_pair = True
            if self.card_suits[card.suit] >= 4:
                has_flush_draw = True

        max_board_rank = 0
        for rank in range(13):
            if self.card_ranks[rank] == 0:
                self.card_ranks[rank] = 1
                if is_straight(self.card_ranks):
                    has_straight_draw = True
                self.card_ranks[rank] = 0 
            elif self.card_ranks[rank] == 1 and self.my_cards[0].rank != rank and self.my_cards[1].rank != rank:
                max_board_rank = max(rank, max_board_rank)
            elif self.card_ranks[rank] == 2 and (self.my_cards[0].rank != rank or self.my_cards[1].rank != rank):
                max_board_rank = max(rank, max_board_rank)
        
        num_overcards = sum([1 for card in self.my_cards if card.rank > max_board_rank])
    
        return has_pair, has_flush_draw, has_straight_draw, num_overcards

    def legal_raise(self, raise_amount: int, round_state, active):
        legal_actions = round_state.legal_actions()
        if RaiseAction in legal_actions:
            min_raise, max_raise = round_state.raise_bounds()
            my_stack = round_state.stacks[active]
            if min_raise > my_stack:
                return check_call_action(round_state)
            else:
                return RaiseAction(min(raise_amount, my_stack))
        else:
            return check_call_action(round_state)
        
    def get_action(self, game_state, round_state, active):
        street = round_state.street  # int representing pre-flop, flop, turn, or river respectively
        board_cards = round_state.deck[:street]  # the board cards
        my_pip = round_state.pips[active]  # the number of chips you have contributed to the pot this round of betting
        opp_pip = round_state.pips[1-active]  # the number of chips your opponent has contributed to the pot this round of betting
        my_stack = round_state.stacks[active]  # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active]  # the number of chips your opponent has remaining
        continue_cost = opp_pip - my_pip  # the number of chips needed to stay in the pot
        my_contribution = STARTING_STACK - my_stack  # the number of chips you have contributed to the pot
        opp_contribution = STARTING_STACK - opp_stack  # the number of chips your opponent has contributed to the pot
        pot_total = my_contribution + opp_contribution
        pot_odds = continue_cost / (pot_total + continue_cost)

        min_raise, max_raise = round_state.raise_bounds()  # the smallest and largest numbers of chips for a legal bet/raise

        if can_win_by_folding(game_state, round_state, active):
            return check_fold_action(round_state)
        
        if street != self.previous_street:
            self.handle_new_street(game_state, round_state, active)

        if street < 3:
            return self.preflop_action(game_state, round_state, active)         
        
        if street == 3 and classify_boards(board_cards) == "Heavy":
            raise_amount = int(my_pip + continue_cost + 0.75 * (pot_total + continue_cost))
        elif street == 3:
            raise_amount = int(my_pip + continue_cost + 0.3 * (pot_total + continue_cost))
        elif street == 4:
            raise_amount = int(my_pip + continue_cost + random.uniform(0.6, 1) * pot_total)
        elif street >= 5:
            raise_amount = int(my_pip + continue_cost + pot_total)
        else:
            raise_amount = min_raise

        raise_amount = max([min_raise, raise_amount])
        raise_amount = min([max_raise, raise_amount])
        

        if continue_cost > 0:
            pot_odds = continue_cost / (pot_total + continue_cost)
            if self.strength  > pot_odds:
                if random.random() < self.strength and self.strength > 0.5:
                    return self.legal_raise(raise_amount, round_state, active)
                else:
                    return CallAction()
            elif self.is_bluffing:
                return self.legal_raise(raise_amount, round_state, active)
            else:
                return check_fold(round_state)
        else:
            if random.random() < self.strength:
                return self.legal_raise(raise_amount, round_state, active)

            else:
                return CheckAction()

        return check_fold(round_state)

if __name__ == '__main__':
    run_bot(Player(), parse_args())