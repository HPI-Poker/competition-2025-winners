import eval7
import os
import time
import json
import subprocess
import socket

from stats import GameSummary
from config import GAME_LOGS_PATH, BOT_LOGS_PATH, NUM_ROUNDS, SMALL_BLIND, BIG_BLIND, STARTING_STACK, STARTING_GAME_CLOCK, CONNECT_TIMEOUT, BUILD_TIMEOUT, ENFORCE_GAME_CLOCK, PLAYER_LOG_SIZE_LIMIT, PLAYER1_NAME, PLAYER1_PATH, PLAYER2_NAME, PLAYER2_PATH, DOCKERIZE_BOTS, PLAYER1_PORT, PLAYER2_PORT
from collections import namedtuple
from queue import Queue
from threading import Thread
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Socket encoding scheme:
#
# T#.### the player's game clock
# P# the player's index
# H**,** the player's hand in common format
# F a fold action in the round history
# C a call action in the round history
# K a check action in the round history
# R### a raise action in the round history
# B**,**,**,**,** the board cards in common format
# O**,** the opponent's hand in common format
# D### the player's bankroll delta from the round
# Q game over
#
# Clauses are separated by spaces
# Messages end with '\n'
# The engine expects a response of K at the end of the round as an ack,
# otherwise a response which encodes the player's action
# Action history is sent once, including the player's actions

FoldAction = namedtuple('FoldAction', [])
CallAction = namedtuple('CallAction', [])
CheckAction = namedtuple('CheckAction', [])
RaiseAction = namedtuple('RaiseAction', ['amount'])
TerminalState = namedtuple('TerminalState', ['deltas', 'previous_state'])

STREET_NAMES = ['Flop', 'Turn', 'River']
DECODE = {'F': FoldAction, 'C': CallAction, 'K': CheckAction, 'R': RaiseAction}
CCARDS = lambda cards: ','.join(map(str, cards))
PCARDS = lambda cards: '[{}]'.format(' '.join(map(str, cards)))
PVALUE = lambda name, value: ', {} ({})'.format(name, value)
STATUS = lambda players: ''.join([PVALUE(p.name, p.bankroll) for p in players])

class Player():
    '''
    Handles subprocess and socket interactions with one player's pokerbot.
    '''

    def __init__(self, name, path, match_id, index):
        self.match_id = match_id
        self.name = name
        self.index = index
        self.path = os.path.join(BASE_DIR, path)
        self.game_clock = STARTING_GAME_CLOCK
        self.bankroll = 0
        self.commands = None
        self.bot_subprocess = None
        self.socketfile = None
        self.bytes_queue = Queue()
        self.player_connection = None if DOCKERIZE_BOTS else PlayerConnection(self.name, self.path, BUILD_TIMEOUT)

    def build(self):
        '''
        Loads the commands file and builds the pokerbot.
        '''
        try:
            with open(os.path.join(self.path, 'commands.json'), 'r') as json_file:
                commands = json.load(json_file)
            if ('build' in commands and 'run' in commands and
                    isinstance(commands['build'], list) and
                    isinstance(commands['run'], list)):
                self.commands = commands
            else:
                print(self.name, 'commands.json missing command "build" or "run"')
        except FileNotFoundError:
            print(self.name, 'commands.json not found - check PLAYER_PATH:', self.path, 'If you started the engine in a docker container (e.g. with docker-compose), you might have to set the DOCKERIZE_BOTS=true environment variable.')
        except json.decoder.JSONDecodeError:
            print(self.name, 'commands.json misformatted')

        if self.player_connection is not None and self.commands is not None and len(self.commands['build']) > 0:
            try:
                proc = self.player_connection.build(self.commands['build'])
                if proc is not None:
                    self.bytes_queue.put(proc.stdout)
            except subprocess.TimeoutExpired as timeout_expired:
                error_message = 'Timed out waiting for ' + self.name + ' to build'
                print(error_message)
                self.bytes_queue.put(timeout_expired.stdout)
                self.bytes_queue.put(error_message.encode())
            except (TypeError, ValueError) as e:
                print(e)
                print(self.name, 'build command misformatted')
                self.bytes_queue.put(str(e).encode())
            except OSError as e:
                print(e)
                print(self.name, 'build failed - check "build" in commands.json')
                self.bytes_queue.put(str(e).encode())
            except Exception as e:
                print(e)
                self.bytes_queue.put(str(e).encode())

    def run_containerized(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            port = (PLAYER1_PORT if self.index == 0 else PLAYER2_PORT)
            with server_socket:
                print('start listening on port {} for {}'.format(port, self.name), flush=True)
                server_socket.bind(('', port))
                server_socket.settimeout(CONNECT_TIMEOUT)
                server_socket.listen()
                port = server_socket.getsockname()[1]
                # block until we timeout or the player connects
                client_socket, _ = server_socket.accept()
                with client_socket:
                    client_socket.settimeout(CONNECT_TIMEOUT)
                    sock = client_socket.makefile('rw')
                    self.socketfile = sock
                    print(self.name, 'connected successfully', flush=True)
        except (TypeError, ValueError) as e:
            print(e)
            print(self.name, 'run command misformatted')
        except socket.timeout:
            print('Timed out waiting for', self.name, 'to connect. Check if the bot is running and the port is open. Did you forget to set the DOCKERIZE_BOTS=false environment variable?')
        except OSError as e:
            print(self.name, 'run failed - check "run" in commands.json;', e)

    def run(self):
        '''
        Runs the pokerbot and establishes the socket connection.
        '''
        if self.player_connection is not None and self.commands is not None and len(self.commands['run']) > 0:
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                with server_socket:
                    server_socket.bind(('', 0))
                    server_socket.settimeout(CONNECT_TIMEOUT)
                    server_socket.listen()
                    port = server_socket.getsockname()[1]
                    proc = self.player_connection.run(self.commands['run'] + [str(port)], port)
                    self.bot_subprocess = proc
                    # function for bot listening
                    def enqueue_output(out, queue):
                        try:
                            for line in out:
                                queue.put(line)
                        except ValueError:
                            pass
                    # start a separate bot listening thread which dies with the program
                    Thread(target=enqueue_output, args=(proc.stdout, self.bytes_queue), daemon=True).start()
                    # block until we timeout or the player connects
                    client_socket, _ = server_socket.accept()
                    with client_socket:
                        client_socket.settimeout(CONNECT_TIMEOUT)
                        sock = client_socket.makefile('rw')
                        self.socketfile = sock
                        print(self.name, 'connected successfully')
            except (TypeError, ValueError) as e:
                print(e)
                print(self.name, 'run command misformatted')
            except socket.timeout:
                print('Timed out waiting for', self.name, 'to connect')
            except OSError:
                print(self.name, 'run failed - check "run" in commands.json')

    def stop(self):
        '''
        Closes the socket connection and stops the pokerbot.
        '''
        if self.socketfile is not None:
            try:
                self.socketfile.write('Q\n')
                self.socketfile.close()
            except socket.timeout:
                print('Timed out waiting for', self.name, 'to disconnect')
            except OSError:
                print('Could not close socket connection with', self.name)
        if self.bot_subprocess is not None:
            try:
                outs, _ = self.bot_subprocess.communicate(timeout=CONNECT_TIMEOUT)
                self.bytes_queue.put(outs)
            except subprocess.TimeoutExpired:
                print('Timed out waiting for', self.name, 'to quit')
                self.bot_subprocess.kill()
                outs, _ = self.bot_subprocess.communicate()
                self.bytes_queue.put(outs)

        # When bots are dockerized we don't have access to their logs in the engine
        if not DOCKERIZE_BOTS:
            logs_dir = os.path.join(BASE_DIR, BOT_LOGS_PATH)
            os.makedirs(logs_dir, exist_ok=True)
            with open(os.path.join(logs_dir, self.match_id + "_" + self.name + '.txt'), 'wb') as log_file:
                bytes_written = 0
                for output in self.bytes_queue.queue:
                    try:
                        bytes_written += log_file.write(output)
                        if bytes_written >= PLAYER_LOG_SIZE_LIMIT:
                            break
                    except TypeError:
                        pass

    def query(self, round_state, player_message, game_log, summary: GameSummary):
        '''
        Requests one action from the pokerbot over the socket connection.
        At the end of the round, we request a CheckAction from the pokerbot.
        '''
        legal_actions = round_state.legal_actions() if isinstance(round_state, RoundState) else {CheckAction}
        if self.socketfile is not None and self.game_clock > 0.:
            clause = ''
            try:
                player_message[0] = 'T{:.3f}'.format(self.game_clock)
                message = ' '.join(player_message) + '\n'
                del player_message[1:]  # do not send redundant action history
                start_time = time.perf_counter()
                self.socketfile.write(message)
                self.socketfile.flush()
                clause = self.socketfile.readline().strip()
                end_time = time.perf_counter()
                if ENFORCE_GAME_CLOCK:
                    self.game_clock -= end_time - start_time
                if self.game_clock <= 0.:
                    print("timeout")
                    raise socket.timeout
                action = DECODE[clause[0]]
                if action in legal_actions:
                    if clause[0] == 'R':
                        amount = int(clause[1:])
                        min_raise, max_raise = round_state.raise_bounds()
                        if min_raise <= amount <= max_raise:
                            return action(amount)
                    else:
                        return action()
                game_log.append(self.name + ' attempted illegal ' + action.__name__)
                summary.add_illegal_action(self.name)
            except socket.timeout:
                error_message = self.name + ' ran out of time'
                game_log.append(error_message)
                print(error_message)
                self.game_clock = 0.
                summary.add_timeout(self.name)
            except OSError:
                error_message = self.name + ' disconnected'
                game_log.append(error_message)
                print(error_message)
                self.game_clock = 0.
            except (IndexError, KeyError, ValueError):
                game_log.append(self.name + ' response misformatted: ' + str(clause))
        return CheckAction() if CheckAction in legal_actions else FoldAction()


class PlayerConnection():
    def __init__(self, name, path, build_timeout):
        self.name = name
        self.path = path
        self.build_timeout = build_timeout

    def build(self, command_string):
        return subprocess.run(command_string,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self.path, timeout=self.build_timeout, check=False)

    def run(self, command_string, port):
        return subprocess.Popen(command_string,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self.path)


class RoundState(namedtuple('_RoundState', ['button', 'street', 'final_street', 'pips', 'stacks', 'hands', 'deck', 'reached_run', 'previous_state'])):
    '''
    Encodes the game tree for one round of poker.
    '''

    # Showdown street is no longer guaranteed to be street == 5
    # Need to include check on final card dealt whether it is a black card (clubs or spades)

    def showdown(self, summary: GameSummary):
        '''
        Compares the players' hands and computes payoffs.
        '''
        score0 = eval7.evaluate(self.deck.peek(self.final_street) + self.hands[0])
        score1 = eval7.evaluate(self.deck.peek(self.final_street) + self.hands[1])
        if score0 > score1:
            delta = STARTING_STACK - self.stacks[1]
        elif score0 < score1:
            delta = self.stacks[0] - STARTING_STACK
        else:  # split the pot
            delta = (self.stacks[0] - self.stacks[1]) // 2
            summary.num_chops += 1
        return TerminalState([delta, -delta], self)

    def legal_actions(self):
        '''
        Returns a set which corresponds to the active player's legal moves.
        '''
        active = self.button % 2
        continue_cost = self.pips[1-active] - self.pips[active]
        if continue_cost == 0:
            # we can only raise the stakes if both players can afford it
            bets_forbidden = (self.stacks[0] == 0 or self.stacks[1] == 0)
            return {CheckAction} if bets_forbidden else {CheckAction, RaiseAction}
        # continue_cost > 0
        # similarly, re-raising is only allowed if both players can afford it
        raises_forbidden = (continue_cost == self.stacks[active] or self.stacks[1-active] == 0)
        return {FoldAction, CallAction} if raises_forbidden else {FoldAction, CallAction, RaiseAction}

    def raise_bounds(self):
        '''
        Returns a tuple of the minimum and maximum legal raises.
        '''
        active = self.button % 2
        continue_cost = self.pips[1-active] - self.pips[active]
        max_contribution = min(self.stacks[active], self.stacks[1-active] + continue_cost)
        min_contribution = min(max_contribution, continue_cost + max(continue_cost, BIG_BLIND))
        return (self.pips[active] + min_contribution, self.pips[active] + max_contribution)

    def proceed_street(self, summary: GameSummary):
        '''
        Resets the players' pips and advances the game tree to the next round of betting.
        '''
        # if self.street == 5:
        #     return self.showdown()
        if self.street == self.final_street:
            return self.showdown(summary)
        new_street = 3 if self.street == 0 else self.street + 1
        if self.street < 5: 
            reached_run = -1 
        elif self.street == 5:
            reached_run = self.stacks[0]
        else:
            reached_run = self.reached_run
        return RoundState(1, new_street, self.final_street, [0, 0], self.stacks, self.hands, self.deck, reached_run, self)

    def proceed(self, action, summary: GameSummary):
        '''
        Advances the game tree by one action performed by the active player.
        '''
        active = self.button % 2
        if isinstance(action, FoldAction):
            delta = self.stacks[0] - STARTING_STACK if active == 0 else STARTING_STACK - self.stacks[1]
            return TerminalState([delta, -delta], self)
        if isinstance(action, CallAction):
            if self.button == 0:  # sb calls bb
                return RoundState(1, 0, self.final_street, [BIG_BLIND] * 2, [STARTING_STACK - BIG_BLIND] * 2, self.hands, self.deck, self.reached_run, self)
            # both players acted
            new_pips = list(self.pips)
            new_stacks = list(self.stacks)
            contribution = new_pips[1-active] - new_pips[active]
            new_stacks[active] -= contribution
            new_pips[active] += contribution
            state = RoundState(self.button + 1, self.street, self.final_street, new_pips, new_stacks, self.hands, self.deck, self.reached_run, self)
            return state.proceed_street(summary)
        if isinstance(action, CheckAction):
            if (self.street == 0 and self.button > 0) or self.button > 1:  # both players acted
                return self.proceed_street(summary)
            # let opponent act
            return RoundState(self.button + 1, self.street, self.final_street, self.pips, self.stacks, self.hands, self.deck, self.reached_run, self)
        # isinstance(action, RaiseAction)
        new_pips = list(self.pips)
        new_stacks = list(self.stacks)
        contribution = action.amount - new_pips[active]
        new_stacks[active] -= contribution
        new_pips[active] += contribution
        return RoundState(self.button + 1, self.street, self.final_street, new_pips, new_stacks, self.hands, self.deck, self.reached_run, self)



class GameConfig:
    def __init__(self, player_1_name, player_1_path, player_2_name, player_2_path, match_id='match'):
        self.player1_name = self.sanitize_filename(player_1_name)
        self.player1_path = os.path.join(BASE_DIR, player_1_path)
        self.player2_name = self.sanitize_filename(player_2_name)
        self.player2_path = os.path.join(BASE_DIR, player_2_path)
        date_id = time.strftime('%Y%m%d%H%M%S')
        self.match_id = self.sanitize_filename(match_id) + "_" + date_id
        self.gamelog_name = self.match_id + "_" + self.player1_name + '_vs_' + self.player2_name

    def sanitize_filename(self, name):
        return re.sub(r'[^a-zA-Z0-9_\-]', '_', name.lower())

class Game():
    '''
    Manages logging and the high-level game procedure.
    '''

    def __init__(self, game_config):
        self.config = game_config
        self.log = ['0.02 HPI Pokerbots - ' + self.config.player1_name + ' vs ' + self.config.player2_name]
        self.player_messages = [[], []]
        players = (self.config.player1_name, self.config.player2_name)
        self.summary = GameSummary(players, self.config.match_id)

    def log_round_state(self, players, round_state):
        '''
        Incorporates RoundState information into the game log and player messages and game summaries.
        '''
        if round_state.street == 0 and round_state.button == 0:
            self.log.append('{} posts the blind of {}'.format(players[0].name, SMALL_BLIND))
            self.log.append('{} posts the blind of {}'.format(players[1].name, BIG_BLIND))
            self.log.append('{} dealt {}'.format(players[0].name, PCARDS(round_state.hands[0])))
            self.log.append('{} dealt {}'.format(players[1].name, PCARDS(round_state.hands[1])))
            self.player_messages[0] = ['T0.', 'P0', 'H' + CCARDS(round_state.hands[0])]
            self.player_messages[1] = ['T0.', 'P1', 'H' + CCARDS(round_state.hands[1])]
        elif round_state.street > 0 and round_state.button == 1:
            board = round_state.deck.peek(round_state.street)
            street_name = STREET_NAMES[round_state.street - 3] if round_state.street < 6 else 'Run'
            self.log.append(street_name + ' ' + PCARDS(board) +
                            PVALUE(players[0].name, STARTING_STACK-round_state.stacks[0]) +
                            PVALUE(players[1].name, STARTING_STACK-round_state.stacks[1]))
            compressed_board = 'B' + CCARDS(board)
            self.player_messages[0].append(compressed_board)
            self.player_messages[1].append(compressed_board)

    def record_pfr(self, name, action, can_raise):
        if can_raise:
            self.summary.add_pfr_opportunity(name)
            if isinstance(action, RaiseAction):
                self.summary.add_pfr(name)
    
    def record_vpip(self, name, action):
        self.summary.add_vpip_opportunity(name)
        if (isinstance(action, CallAction) or isinstance(action, RaiseAction)):
            self.summary.add_vpip(name)

    def record_preflop_action(self, name, action, can_raise):
        self.record_vpip(name, action)
        self.record_pfr(name, action, can_raise)

    def record_action_for_stats(self, name, action, is_pre_flop_action, can_raise):
        if is_pre_flop_action:
            self.record_preflop_action(name, action, can_raise)

    def log_action(self, name, action, bet_override):
        '''
        Incorporates action information into the game log and player messages and game summaries.
        '''
        if isinstance(action, FoldAction):
            phrasing = ' folds'
            code = 'F'
        elif isinstance(action, CallAction):
            phrasing = ' calls'
            code = 'C'
        elif isinstance(action, CheckAction):
            phrasing = ' checks'
            code = 'K'
        else:  # isinstance(action, RaiseAction)
            phrasing = (' bets ' if bet_override else ' raises to ') + str(action.amount)
            code = 'R' + str(action.amount)
        self.log.append(name + phrasing)
        self.player_messages[0].append(code)
        self.player_messages[1].append(code)

    def summarize_round(self, players, round_state, round_num: int):
        name_to_delta = {players[0].name: round_state.deltas[0], players[1].name: round_state.deltas[1]}
        self.summary.add_round(round_num, name_to_delta)

    def log_terminal_state(self, players, round_state):
        '''
        Incorporates TerminalState information into the game log and player messages and summary.
        '''
        previous_state = round_state.previous_state
        if FoldAction not in previous_state.legal_actions():
            self.log.append('{} shows {}'.format(players[0].name, PCARDS(previous_state.hands[0])))
            self.log.append('{} shows {}'.format(players[1].name, PCARDS(previous_state.hands[1])))
            self.player_messages[0].append('O' + CCARDS(previous_state.hands[1]))
            self.player_messages[1].append('O' + CCARDS(previous_state.hands[0]))
        self.log.append('{} awarded {}'.format(players[0].name, round_state.deltas[0]))
        self.log.append('{} awarded {}'.format(players[1].name, round_state.deltas[1]))
        self.player_messages[0].append('D' + str(round_state.deltas[0]))
        self.player_messages[1].append('D' + str(round_state.deltas[1]))

        if previous_state.reached_run > 0: 
            self.log.append('Run reached')
            pre_run_contribution = STARTING_STACK - previous_state.reached_run
            # print('pre_run_contribution', pre_run_contribution)
            if round_state.deltas[0] > round_state.deltas[1]:
                self.log.append('{} won {}'.format(players[0].name, round_state.deltas[0] - pre_run_contribution))
                self.log.append('{} won {}'.format(players[1].name, round_state.deltas[1] + pre_run_contribution))
            else:
                self.log.append('{} won {}'.format(players[0].name, round_state.deltas[0] + pre_run_contribution))
                self.log.append('{} won {}'.format(players[1].name, round_state.deltas[1] - pre_run_contribution))

    def run_round(self, players, round_num):
        '''
        Runs one round of poker.
        '''

        # ROYAL VARIANT ENTAILS THAT CARDS MAY CONTINUE TO BE DEALT PAST THE RIVER UNTIL A NON-FACE CARD IS DEALT

        deck = eval7.Deck()
        deck.shuffle()
        hands = [deck.deal(2), deck.deal(2)]

        # eval7 card euits are defined as ('c', 'd', 'h', 's')
        
        FINAL_STREET = 5 
        while deck.cards[FINAL_STREET-1].rank in (9, 10, 11): 
            FINAL_STREET += 1
        
        if FINAL_STREET > 48:
            FINAL_STREET = 48

        pips = [SMALL_BLIND, BIG_BLIND]
        stacks = [STARTING_STACK - SMALL_BLIND, STARTING_STACK - BIG_BLIND]
        round_state = RoundState(0, 0, FINAL_STREET, pips, stacks, hands, deck, -1, None)
        while not isinstance(round_state, TerminalState):
            self.log_round_state(players, round_state)
            active = round_state.button % 2
            player:Player = players[active]
            action = player.query(round_state, self.player_messages[active], self.log, self.summary)
            bet_override = (round_state.pips == [0, 0])
            self.log_action(player.name, action, bet_override)

            is_pre_flop_action = (round_state.street == 0)
            can_raise = RaiseAction in round_state.legal_actions()
            self.record_action_for_stats(player.name, action, is_pre_flop_action, can_raise)

            round_state = round_state.proceed(action, self.summary)
        self.log_terminal_state(players, round_state)
        self.summarize_round(players, round_state, round_num)
        for player, player_message, delta in zip(players, self.player_messages, round_state.deltas):
            player.query(round_state, player_message, self.log, self.summary)
            player.bankroll += delta

    def run(self):
        print('Starting the pbc engine...', flush=True)
        players = [
            Player(self.config.player1_name, self.config.player1_path, self.config.match_id, 0),
            Player(self.config.player2_name, self.config.player2_path, self.config.match_id, 1)
        ]
        for player in players:
            if DOCKERIZE_BOTS:
                player.run_containerized()
            else:
                player.build()
                player.run()
        print(f'Players connected successfully. Starting {NUM_ROUNDS} rounds...', flush=True)
        for round_num in range(1, NUM_ROUNDS + 1):
            self.log.append('===')
            self.log.append('Round #' + str(round_num) + STATUS(players))
            if round_num % (NUM_ROUNDS // 10) == 0:
                name_to_bankrolls = {player.name: player.bankroll for player in players}
                self.summary.add_bankrolls(round_num, name_to_bankrolls)
            self.run_round(players, round_num)
            players = players[::-1]
        self.log.append('')
        self.log.append('Final' + STATUS(players))
        
        for player in players:
            player.stop()
        name = self.config.gamelog_name + '.log'

        gamelogs_path = os.path.join(BASE_DIR, GAME_LOGS_PATH)
        print('Writing logs to', os.path.normpath(os.path.join(gamelogs_path, name)))
        os.makedirs(gamelogs_path, exist_ok=True)

        with open(os.path.join(gamelogs_path, name), 'w') as log_file:
            log_file.write('\n'.join(self.log))

        print('Players:', self.config.player1_name, 'vs.', self.config.player2_name)
        print('Result:', self.summary.discretized_bankrolls[-1][1][0], 'vs.', self.summary.discretized_bankrolls[-1][1][1])

        self.summary.set_logs(self.log)
        self.summary.write_summary()
        

if __name__ == '__main__':
    Game(GameConfig(
        PLAYER1_NAME,
        PLAYER1_PATH,
        PLAYER2_NAME,
        PLAYER2_PATH
    )).run()
