#include <cstdint>
#include <omp/Hand.h>
#include <omp/HandEvaluator.h>
#include <omp/Constants.h>
#include <map>
#include <random>
#include <algorithm>
#include <ranges>
#include <immintrin.h>
#include <iostream>
#include <iomanip>
#include <thread>

using namespace omp;
using namespace std;
#include "preflop.h"

const uint8_t JACK = 9;
const uint8_t QUEEN = 10;
const uint8_t KING = 11;

bool are_cards_suited(const array<uint8_t,2>& cards) {
    return cards[0] % SUIT_COUNT == cards[1] % SUIT_COUNT;
}

bool is_pair(const array<uint8_t,2>& cards) {
    return cards[0] / SUIT_COUNT == cards[1] / SUIT_COUNT;
}

bool are_cards_connected(const array<uint8_t,2>& cards) {
    return abs(cards[0] / (int)SUIT_COUNT - cards[1] / (int)SUIT_COUNT) == 1;
}

bool has_high_card(const array<uint8_t,2>& cards) {
    return cards[0] / SUIT_COUNT >= QUEEN || cards[1] / SUIT_COUNT >= QUEEN;
}

bool is_blind_bandit_good(const array<uint8_t,2>& hand) {
    return are_cards_suited(hand) || is_pair(hand) || are_cards_connected(hand) || has_high_card(hand);
}

bool is_face(uint8_t card) {
    uint8_t rank = card / SUIT_COUNT;
    return JACK <= rank && rank <= KING;
}

mt19937 rng(0);
auto random_bit = uniform_int_distribution<uint64_t>(0, CARD_COUNT - 1);

uint64_t draw(uint64_t used, int n) {
    uint64_t result = 0;
    for (int i = 0; i < n; ++i) {
        uint64_t bit;
        do bit = 1ull << random_bit(rng); while (used & bit);
        result |= bit, used |= bit;
        if (i == n - 1) n += is_face(countr_zero(bit));
    }
    return result;
}

Hand from_bitmask(uint64_t mask) {
    Hand h = Hand::empty();
    while (mask) {
        int tz = countr_zero(mask);
        h += tz;
        mask ^= 1ull << tz;
    }
    return h;
}

HandEvaluator eval;
uint16_t evaluate(uint64_t hand) {
    int cards = popcount(hand);
    if (cards <= 7)
        return eval.evaluate(from_bitmask(hand));
    uint16_t best = 0;
    uint64_t x = (1 << 7) - 1;
    while (x < (1 << cards)) {
        uint64_t hand7 = _pdep_u64(x, hand);
        best = max(best, eval.evaluate(from_bitmask(hand7)));

        uint64_t c = x&-x, r = x+c;
        x = (((r^x) >> 2)/c) | r;
    }
    return best;
}

double monte_carlo(const array<uint8_t,2>& me, const vector<array<uint8_t,2>> &opponent, uint64_t board = 0, uint8_t last = 0, double err = 1, int min_iters = 100, auto duration = chrono::minutes(1), uint64_t dead = 0) {
    auto start = chrono::steady_clock::now();
    int n = max(0, 5 - popcount(board));
    if (n == 0 && is_face(last)) n = 1;
    dead |= 1ull << me[0];
    dead |= 1ull << me[1];
    dead |= board;
    uint64_t my_hand = (1ull << me[0]) | (1ull << me[1]) | board;

    uint64_t total = 0, wins = 0;
    vector<uint64_t> opponent_hands;
    for (const auto& opp : opponent) {
        uint64_t opp_hand = (1ull << opp[0]) | (1ull << opp[1]);
        if (opp_hand & dead) continue;
        opponent_hands.push_back(opp_hand | board);
    }
    double ntrials, p, stdev, confidence;
    do {
        uint64_t playout = draw(dead, n);
        auto my_score = evaluate(my_hand | playout);
        for (const auto& opp : opponent_hands) {
            if (opp & playout) continue;
            ++total;
            auto opp_score = evaluate(opp | playout);
            wins += (my_score >= opp_score) + (my_score > opp_score);
        }
        ntrials = (double)total / size(opponent_hands);
        p = wins / 2.0 / total;
        stdev = sqrt(p * (1 - p));
        confidence = 1.96 * stdev / sqrt(ntrials);
    } while (chrono::steady_clock::now() - start < duration && !(
            ntrials >= min_iters &&
            confidence <= err
    ));
    return p;
}

uint8_t string_to_card(string const &s) {
    string ranks{"23456789TJQKA"}, suits{"shcd"};
    return (find(begin(ranks), end(ranks), s[0]) - begin(ranks)) * 4 +
           (find(begin(suits), end(suits), s[1]) - begin(suits));
}

vector<array<uint8_t,2>> hands_except(const vector<uint8_t> &forbidden_cards) {
    vector<bool> allowed(CARD_COUNT, true);
    for (auto card : forbidden_cards) allowed[card] = false;
    vector<uint8_t> good;
    for (uint8_t i = 0; i < CARD_COUNT; ++i) if (allowed[i]) good.push_back(i);
    vector<array<uint8_t,2>> result;
    for (size_t i = 0; i < size(good); ++i)
        for (size_t j = i + 1; j < size(good); ++j)
            result.push_back({good[i], good[j]});
    return result;
}

array<uint8_t,2> hand_rep(array<uint8_t,2> hand) {
    if (hand[0] < hand[1]) swap(hand[0], hand[1]);
    return {
            static_cast<uint8_t>(hand[0] & RANK_MASK),
            static_cast<uint8_t>((hand[1] & RANK_MASK) | ((hand[0] & SUIT_MASK) != (hand[1] & SUIT_MASK)))
    };
}

double equity(array<uint8_t,2> hand, vector<uint8_t> board, auto duration) {
    vector<uint8_t> dead{board}; dead.insert(end(dead), begin(hand), end(hand));
    uint64_t board_mask = 0;
    for (auto x : board) board_mask |= 1ull << x;
    if (!board_mask)
        return preflop[hand_rep(hand)];

    vector<array<uint8_t,2>> opponent = hands_except(dead);
    double err = 2e-3; int min_iters = 100;
    return monte_carlo(hand, opponent, board_mask, empty(board) ? 0 : board.back(), err, min_iters, duration);
}
double equity(array<string,2> hand_string, vector<string> board_string, auto duration) {
    array<uint8_t,2> hand{};
    vector<uint8_t> board(size(board_string));
    transform(begin(hand_string), end(hand_string), begin(hand), string_to_card);
    transform(begin(board_string), end(board_string), begin(board), string_to_card);
    return equity(hand, board, duration);
}

/*
int main() {
    cout << setprecision(4) << fixed;
    cout << "map<array<uint8_t,2>,double> preflop{";
    for (int i = 0; i < 13; i++) {
        uint8_t card = i * SUIT_COUNT;
        for (int j = 0; j < 13; j++) {
            uint8_t card2 = j * SUIT_COUNT + (j <= i);
            array hand{card, card2};
            hand = hand_rep(hand);
            double eq = equity(hand, {}, chrono::minutes(2));
            cout << "{array<uint8_t,2>{" << int(hand[0]) << ", " << int(hand[1]) << "}, " << eq << "}," << flush;
        }
    }
    cout << "};";
}
 */