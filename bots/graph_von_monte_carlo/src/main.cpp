#include <skeleton/actions.h>
#include <skeleton/constants.h>
#include <skeleton/runner.h>
#include <skeleton/states.h>
#include <chrono>
#include "util.cpp"

using namespace pokerbots::skeleton;

struct Bot {
    mt19937 rng{42};
    uniform_real_distribution<double> U{0, 1};
    static void handleRoundOver(const GameInfoPtr& gameState, const TerminalStatePtr&, int) {
        cerr << gameState->roundNum << ": " << gameState->bankroll << " " << gameState->gameClock << endl;
    }
    void handleNewRound(const GameInfoPtr&, const RoundStatePtr&, int) {}
#define pip(player) (100-roundState->stacks[player])
    bool canWinByFolding(const GameInfoPtr& gameState, const RoundStatePtr& roundState, int active) {
        auto rounds_left = NUM_ROUNDS - gameState->roundNum + 1;
        auto loss = rounds_left / 2 * 3;
        if (rounds_left % 2 == 1) loss += pip(active);
        return gameState->bankroll - loss > 4;
    }


    Action checkCall(const auto &legalActions) {
        return legalActions.contains(Action::Type::CHECK) ? Action{Action::Type::CHECK} : Action{Action::Type::CALL};
    }

    Action getAction(const GameInfoPtr& gameState, const RoundStatePtr& roundState, int active) {
        auto [minRaise, maxRaise] = roundState->raiseBounds();
        if (roundState->stacks[active] == 0) return Action{Action::Type::CHECK};
        if (canWinByFolding(gameState, roundState, active)) {
            // cerr << "I can win by folding. Nananana" << endl;
            return Action{Action::Type::FOLD};
        }
        auto legalActions = roundState->legalActions();
        if (gameState->roundNum == NUM_ROUNDS && gameState->bankroll < 0 && gameState->bankroll >= -100) {
            if (legalActions.contains(Action::Type::RAISE)) return Action{Action::Type::RAISE, maxRaise};
        }
        auto rounds_left = NUM_ROUNDS - gameState->roundNum;
        auto duration = chrono::nanoseconds((long long)(1e9 * (gameState->gameClock-1) / rounds_left));

        double eq = equity(roundState->hands[active], roundState->deck, 1/1.8*duration);
        if (roundState->street == 0 && eq > 0.45 && pip(active) == 1) {
            int raise = clamp(5 - pip(active), minRaise, maxRaise);
            return Action{Action::Type::RAISE, raise};
        }

        if (legalActions.contains(Action::Type::CHECK)) {
            // Check or Raise
            if (eq >= 0.55 && legalActions.contains(Action::Type::RAISE)) {
                double wishraise = 1.67 * pip(active);
                if (eq >= 0.6) wishraise = 2 * pip(active);
                if (eq >= 0.7) wishraise = 3 * pip(active);
                int raise = clamp((int) llround(wishraise - pip(active)), minRaise, maxRaise);
                return Action{Action::Type::RAISE, raise};
            }
            return Action{Action::Type::CHECK};
        } else {
            // Call or Fold, let's not reraise.
            double eqp = eq - 0.001 * (pip(1 - active) - pip(active));
            if (eqp >= 0.5) {
                /*
                cerr << "Hand: " << roundState->hands[active][0] << roundState->hands[active][1] << endl;
                cerr << "Board: ";
                for (auto card : roundState->deck) cerr << card;
                cerr << endl;
                cerr << "Expected pot value: " << expected_pot_value << " pip " << pip(1 - active) << endl;
                cerr << "Equity: " << eq << endl;
                 */
                return Action{Action::Type::CALL};
            }
            return Action{Action::Type::FOLD};
        }
    }
};

int main(int argc, char *argv[]) {
    auto [host, port] = parseArgs(argc, argv);
    runBot<Bot>(host, port);
    return 0;
}