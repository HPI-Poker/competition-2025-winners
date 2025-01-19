'''
Simple example pokerbot, written in Python.
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot
import random

# ----------------------------- Helper Functions -----------------------------

def card_rank_to_int(card_rank) -> int:
    mapping = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10}
    if card_rank in mapping:
        return mapping[card_rank]
    return int(card_rank)

def are_cards_suited(cards) -> bool:
    return cards[0][1] == cards[1][1]

def is_pair(cards) -> bool:
    return cards[0][0] == cards[1][0]

def are_cards_connected(cards) -> bool:
    return abs(card_rank_to_int(cards[0][0]) - card_rank_to_int(cards[1][0])) == 1

def has_high_card(cards) -> bool:
    return cards[0][0] in ['Q', 'K', 'A'] or cards[1][0] in ['Q', 'K', 'A']

def check_fold_action(round_state):
    if CheckAction in round_state.legal_actions():
        return CheckAction()
    return FoldAction()

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
# ---------------------------------------------------------------------------

class Player(Bot):
    '''
    The blind bandit tries to steal the blinds by moving all-in with decent hands.
    However, their patience is limited, and they want to decide the fate of the hand pre-flop.
    Beat it decisively.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.

        Arguments:
        Nothing.

        Returns:
        Nothing.
        '''
        pass

    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        
        pass

    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        terminal_state: the TerminalState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        pass
        

    def get_action(self, game_state, round_state, active):
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs an action from your bot.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Your action.
        '''
        my_cards = round_state.hands[active]
        
        if can_win_by_folding(game_state, round_state, active):
            return check_fold_action(round_state)
        
        go_all_in = any([are_cards_suited(my_cards), is_pair(my_cards), are_cards_connected(my_cards), has_high_card(my_cards)])
        if random.random() < 0.2:
            go_all_in = not go_all_in
        
        if go_all_in:
            if RaiseAction in round_state.legal_actions():
                min_raise, max_raise = round_state.raise_bounds()
                return RaiseAction(max_raise)
            if CallAction in round_state.legal_actions():
                return CallAction()
            return CheckAction() 
        else:
            return check_fold_action(round_state)

if __name__ == '__main__':
    run_bot(Player(), parse_args())