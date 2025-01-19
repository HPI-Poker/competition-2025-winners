import os
from dotenv import load_dotenv

env_file = os.path.join(os.path.dirname(__file__), '../.env')
if os.path.exists(env_file): # in docker container it won't exist but will be set by docker-compose
    load_dotenv(env_file, override=True)

DOCKERIZE_BOTS = os.environ.get('DOCKERIZE_BOTS', 'false').lower() == 'true'

PLAYER1_NAME = os.environ.get('PLAYER1_NAME', 'Player_1')
PLAYER1_PATH = os.environ.get('PLAYER1_PATH', 'bots/python_skeleton')
PLAYER1_PORT = int(os.environ.get('PLAYER1_PORT', '3001'))
PLAYER2_NAME = os.environ.get('PLAYER2_NAME', 'Player_2')
PLAYER2_PATH = os.environ.get('PLAYER2_PATH', 'bots/python_skeleton')
PLAYER2_PORT = int(os.environ.get('PLAYER2_PORT', '3002'))

MATCH_ID = os.environ.get('MATCH_ID', 'match')

PLAYER_LOG_SIZE_LIMIT = int(os.environ.get('PLAYER_LOG_SIZE_LIMIT', '524288'))
ENFORCE_GAME_CLOCK = os.environ.get('ENFORCE_GAME_CLOCK', 'true').lower() == 'true'
STARTING_GAME_CLOCK = float(os.environ.get('STARTING_GAME_CLOCK', '60'))
BUILD_TIMEOUT = float(os.environ.get('BUILD_TIMEOUT', '60'))
CONNECT_TIMEOUT = float(os.environ.get('CONNECT_TIMEOUT', '10'))

NUM_ROUNDS = int(os.environ.get('NUM_ROUNDS', '1000'))
STARTING_STACK = int(os.environ.get('STARTING_STACK', '100'))
BIG_BLIND = int(os.environ.get('BIG_BLIND', '2'))
SMALL_BLIND = int(os.environ.get('SMALL_BLIND', '1'))

BOT_LOGS_PATH = 'logs/bot_logs'
GAME_LOGS_PATH = 'logs/game_logs'
SUMMARY_PATH = 'logs/summary'