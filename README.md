# HPI Showdown 2025
Official Repository of HPI Shodown - the Poker Bot Competition 2025. Additional information can be found in the [Wiki](https://hpi-poker.notion.site). You can find updated information of this `README` under [Framework & Setup](https://hpi-poker.notion.site/Framework-Setup-173bcdee7a5e806d8a49ca144f7b98a0) and [Troubleshooting](https://hpi-poker.notion.site/Troubleshooting-176bcdee7a5e803eaaa7ff846d740280). 

## Developing your Poker Bot
In the bots folder you can find different skeletons for python and C++. Choose your preferred language, copy the corresponding skeleton directory and start implementing your poker bot.

We play a 1v1 version of no limit texas hold'em, and your implementation will control one of the bots. For more information on how to run a game, see section [Running your Poker Bot](./README.md#running-your-poker-bot).

Overall, you will have to implement a class that is called to ask for an action when its the bots turn. You will have to return which action you choose to do. Furthermore, a method will be called when a new round has started and when a round has ended. The `Game`- and `RoundState` are always passed as arguments and contain all information about the state. For further information, please look at the comments and the relevant classes (`player.py` or `src/main.cpp`).

In `commands.json` you can configure how your bot is called. You will most likely not have to change those if you use the same structure as the skeletons. Other files ensure the correct connection between the poker engine and the poker bots. You will not have to change any files other than the main script.

### Installing libraries
Before installing a library you have to check with the HPI Showdown team if this library is allowed. You have to post a message in the related [discord channel](https://discord.com/channels/1308788707389607976/1326184106010087485) with a link to its documentation.

You can install the libraries in the `Dockerfile` of your bot. For python you can also add it to the `requirements.txt`. Make sure that all resources your bot requires are inside of the `Dockerfile` and the directory of the bot.

If you are running your bot without docker you should also add the library to your `environment.yaml`.

### Submission
Before the competitions you will have to push the code of your current bot into the correct subdirectory of the `submission` directory. See `submission/example` as an example structure. We will only consider the code inside of this directory (make sure no files outside of this directory are referenced) that was pushed before the deadline. Edit the `name.txt` to give your bot a name for the final competition.

## Running your Poker Bot
The engine can run an 1v1 poker game consisting of several rounds between two bots. `.env` contains the configuration for your matchup including the paths to the two bots you want to play against each other. The rest of the configuration is setup just as in the final tournament. You may change them while developing e.g. preventing to enforce the game clock to prevent timeouts while debugging your bot.

The final results of your match are shown in the console output. Additionally, a JSON summary with some statistics can be found in `logs/summary`. The `logs/game_logs` contains a standardized format of each round and action taken in the game. Finally, `logs/bot_logs` contains any `stdout`, `stderr` or `print` statements your bot made (if the bot was not containerized with docker). This can be useful for debugging your bot and finding error sources.

There are different ways how you can run a match between two poker bots:

### Locally with Docker (Recommended for Quick Setup)
We recommend using docker to run the poker bot engine because it will save you some time setting up your environment and because this will be how the bots are run in the competitions.

You will only need to install docker. Once the docker engine is running, you can run a game. Specify which bots you want to run by setting the variables `PLAYER1_PATH` and `PLAYER2_PATH` in the `.env` file. Set the `DOCKERIZE_BOTS` variable to `true` and run the game by using docker compose: `docker-compose up`.

Everytime you change something in your code, you have to rebuild the containers. You can do this by running `docker-compose up --build`.

Note:
- The `bot_logs` file of a match will be empty. Your logs will only be found inside of the bot container and in the `docker compose` console.
- The base image for the containers is just build for x86 and ARM. If you have a different architecture, you need to build the base image yourself by running the following command: `docker build -t tjongen/pbc25base -f pbcBase.Dockerfile .`.

### Locally without Docker
For setting the environment up manually you will have to download the required dependencies.
This could take a little longer but especially allows debugging your python bots easily. 

#### Requirements & Setup
As the engine is written in python you can easily setup your environment with [conda](https://docs.anaconda.com/miniconda/miniconda-install/). Then you can run `conda env create -f environment.yml`.

We recommend implementing your bots in python since there is no additional setup required and it allows for easy debugging. If you do decide to implement your bot in a different language you will need to the following requirements:

For running **C++** bots:
- C++ 17 required
- [Boost](https://www.boost.org/) (`sudo apt install libboost-all-dev`)
- [fmt](https://fmt.dev/11.0/get-started/) version >= 9.0.0 required; [10.2.1](https://github.com/fmtlib/fmt/releases/tag/10.2.1) recommended. Note that `apt` might install an older version! 

#### Commands to Run
First, you should define the names and the paths to the directories of your bots in `engine/config.py` that you want to match up. To start a game run:
1. `conda activate pbc`
2. `python engine/engine.py`

After completion, you can find the logs of the players (print statements), game progression (each action per round) and summary (further stats) in the `logs` directory.

#### Debugging your Bot
When you setup your environment locally (without docker!) you can simply debug your python bots in VS Code by adding a breakpoint in the bots script (e.g. `player.py`) and starting the `engine.py` via the debugger. Make sure that the configured paths to the bots are provided relative to the root of the project.

Debugging bots written in C++ is a little more difficult. You will also need to setup `Locally without docker`!
1. Set `DOCKERIZE_BOTS=true` and `ENFORCE_GAME_CLOCK=false` in `.env`.
2. Start your `main.cpp` with your C++ Debugger and pass the `--host localhost 3001`. Make sure this port is the same as `PLAYER1_PORT` in `.env`. The bot should now try to connect to an engine (we will start the engine later)...
3. Start the opponent bot (without debugger), e.g. with `python bot/bot.py --host localhost 3002`. Make sure this port is the same as `PLAYER2_PORT` in `.env`.
4. Start the engine (if you want start it containerized but don't start the bots containers with docker). The engine and the bots should now connect via the given ports.
Otherwise you should try to debug using stdout logs and look at your dockers log files or the generated `logs/bot_logs` files.

## Troubleshooting

### My bot keeps folding even though I didn't code that?
It is possible that your bot failed to build or connect to the engine. The engine is programmed in a way that your bot will still run but will only post blinds, if possible check and otherwise fold.
Check for errors in the logs of the engine like "Timed out waiting for cpp to connect".

If your bot ran out of time (STARTING_GAME_CLOCK is set to 60s accumulated over 1000 rounds) it will automatically post blinds and check if possible but otherwise fold.

### Problems with docker

#### Some changes to my .env file do not have an effect when running with docker in VS Code terminals?
Changing the PLAYER1_PATH, PLAYER1_PORT etc. variables that are used in compose.yaml does not have an effect when running `docker compose up --build` in a VS Code terminal.

Quick fix: Try to open a new VS Code terminal.
In general: This will NOT occur if you run docker compose in a terminal outside of VS Code!

The root of this problem is described here: https://stackoverflow.com/a/78517796/8657837:
- The VS Code python extension automatically sets environment variables from the `.env` file when starting a new terminal. They are not updated if you update your `.env` file!
- The shell environment variables take precedence over variables defined in `.env` when running docker compose for variables used in the compose.yaml. This means that changing your `.env` file does not have an effect on variables like the player path and port.
- To make matters worse: the updated variables are actually passed on to the engine container, e.g. bot names will be updated correctly. Same goes for ports which means that the ports from the engine and the bots will be out of sync and the engine will fail to connect.
- Therefore, you could also reconfigure the `python.env` setting to avoid the Python extension to not load the `.env` file by default.

#### Changes to my bots code do not have an effect when running with docker?
Did you rebuild your images with `docker compose build` or `docker compose up --build`?

#### docker: player1-1 Waiting to connect to engine:3001; [Errno 111] Connection refused
If the engine responds with "player_1 connected successfully" later down the line you can ignore this warning. This is simply a race condition where the engine is started after the bots.
If there are errors afterwards make sure that `DOCKERIZE_BOTS=true` (otherwise the engine will try to find the bot path locally in its container to build and run them but the bots do not exist in that container).


#### Timed out waiting for player1 to connect
Ensure that `DOCKERIZE_BOTS=false` if you start the engine with `python engine/engine.py` (otherwise the engine expects the bots to be started as "stand-alone" processes).
On the other hand, make sure that `DOCKERIZE_BOTS=true` if you start the engine with `docker compose up` (otherwise the engine will try to find the bot path locally in its container to build and run them but the bots do not exist in that container).

#### failed to solve: failed to read dockerfile: open /var/lib/docker/tmp/buildkit-mountxxxxxx/Dockerfile: no such file or directory
You didn't add a `Dockerfile` to your bot. Please look at the skeleton bots for examples.

### C++ build fails
If you get an error like this:
```
> [player2 4/5] RUN ["bash", "build.sh"]:
0.308 build.sh: line 2: $'\r': command not found
" does not exist.: The source directory "/app/build
0.317 Specify --help for usage, or press the help button on the CMake GUI.
0.319 build.sh: line 6: $'make\r': command not found
0.320 build.sh: line 7: cd: $'..\r': No such file or directory
```
Then the line endings of the `build.sh` file of your bot need to be in unix-style (CR). You can change this easily in VS Code bottom right from CRLF.

If you get:
```
exec ./run.sh: no such file or directory
```
Then the line endings of the `run.sh` file of your bot need to be in unix-style (CR). You can change this easily in VS Code bottom right from CRLF.


Otherwise make sure you have the correct versions of the libraries installed. Also, try deleting the `build` directory to clear the cache.

### On GCP 
Use GCP for free Cloud Resources provided by our partner Google. On GCP you can start a VM in the Compute Engine. You will have to set it up to contain the dependencies (especially docker, docker-compose and git).

## Authors
- Philipp Kolbe
- Mehdi Gouasmi
- Anton Hackl
- Tobias Jongen
- Pit Buttchereit

## Acknowledgements
Credits go to [MIT Pokerbots](https://pokerbots.org/) for providing us with the basis for the poker framework.
