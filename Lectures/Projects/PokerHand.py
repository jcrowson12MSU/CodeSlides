"""Classify a 5-card poker hand.

Each card is a fixed 4-character string:
  - characters 0-1: the card value, right-justified with a leading
    space when the value is a single character (e.g. " 4", " K", " A").
    Two-character values like "11" use both characters.
  - character 2: the suit, one of ♠ ♣ ♥ ♦
  - character 3: a trailing separator space

Values: 2-10 (numbers), J, Q, K, A (letters, worth 11-14).

Example hand (two pair): " 4♥ 11♥ 4♣ 10♥ 10♦"

Only if statements, string operations, and mathematical operations
are used to implement the classification logic.
"""

SUITS = "♠♣♥♦"


def card_value(card):
    """Return the numeric value (2-14) of a 4-character card string."""
    text = card[0] + card[1]

    if text == " A":
        return 14
    if text == " K":
        return 13
    if text == " Q":
        return 12
    if text == " J":
        return 11

    # Otherwise it's a plain number: " 2".." 9" or "10"
    return int(text)


def card_suit(card):
    """Return the suit character of a 4-character card string."""
    return card[2]


def value_name(value):
    """Return a human-readable name for a numeric card value."""
    if value == 14:
        return "Ace"
    if value == 13:
        return "King"
    if value == 12:
        return "Queen"
    if value == 11:
        return "Jack"
    return str(value)


def split_hand(hand):
    """Split a hand string into a list of five 4-character card strings."""
    # The final card's trailing separator space is optional.
    if len(hand) == 19:
        hand = hand + " "

    cards = []
    index = 0
    while index < 20:
        cards.append(hand[index:index + 4])
        index = index + 4
    return cards


def sort_values(values):
    """Return a new list with the five values sorted from low to high.

    A simple bubble sort, using only if statements and loops.
    """
    sorted_values = []
    for v in values:
        sorted_values.append(v)

    n = len(sorted_values)
    i = 0
    while i < n:
        j = 0
        while j < n - 1:
            if sorted_values[j] > sorted_values[j + 1]:
                temp = sorted_values[j]
                sorted_values[j] = sorted_values[j + 1]
                sorted_values[j + 1] = temp
            j = j + 1
        i = i + 1

    return sorted_values


def count_value(values, target):
    """Count how many times target appears in values."""
    count = 0
    for v in values:
        if v == target:
            count = count + 1
    return count


def get_counts(values):
    """Return a list of (value, count) for each distinct value in values."""
    counts = []
    for v in values:
        already_have = False
        for pair in counts:
            if pair[0] == v:
                already_have = True
        if not already_have:
            counts.append((v, count_value(values, v)))
    return counts


def highest_count(counts):
    """Return the largest count among (value, count) pairs."""
    best = 0
    for pair in counts:
        if pair[1] > best:
            best = pair[1]
    return best


def second_highest_count(counts):
    """Return the second largest count among (value, count) pairs."""
    best = 0
    second = 0
    for pair in counts:
        if pair[1] > best:
            second = best
            best = pair[1]
        elif pair[1] > second:
            second = pair[1]
    return second


def is_flush(cards):
    """True if all five cards share the same suit."""
    first_suit = card_suit(cards[0])
    all_same = True
    for card in cards:
        if card_suit(card) != first_suit:
            all_same = False
    return all_same


def is_straight(sorted_values):
    """True if the five sorted values form five consecutive ranks.

    Also treats Ace-2-3-4-5 (the "wheel") as a straight.
    """
    # Wheel: A, 2, 3, 4, 5 sorted becomes 2, 3, 4, 5, 14
    if (sorted_values[0] == 2 and sorted_values[1] == 3 and
            sorted_values[2] == 4 and sorted_values[3] == 5 and
            sorted_values[4] == 14):
        return True

    index = 0
    while index < 4:
        if sorted_values[index + 1] - sorted_values[index] != 1:
            return False
        index = index + 1
    return True


def classify_hand(hand):
    """Return the name of the best poker hand ranking for the hand string."""
    cards = split_hand(hand)

    values = []
    for card in cards:
        values.append(card_value(card))

    sorted_values = sort_values(values)
    counts = get_counts(values)

    flush = is_flush(cards)
    straight = is_straight(sorted_values)

    top_count = highest_count(counts)
    next_count = second_highest_count(counts)

    if straight and flush:
        return "Straight Flush"
    if top_count == 4:
        return "Four of a Kind"
    if top_count == 3 and next_count == 2:
        return "Full House"
    if flush:
        return "Flush"
    if straight:
        return "Straight"
    if top_count == 3:
        return "Three of a Kind"
    if top_count == 2 and next_count == 2:
        return "Two Pair"
    if top_count == 2:
        return "One Pair"
    return "High Card"


def format_hand(hand):
    """Return a human-readable version of the hand, for display."""
    cards = split_hand(hand)
    parts = []
    for card in cards:
        value = card_value(card)
        suit = card_suit(card)
        parts.append(value_name(value) + suit)

    result = ""
    index = 0
    while index < len(parts):
        result = result + parts[index]
        if index < len(parts) - 1:
            result = result + ", "
        index = index + 1
    return result


def main():
    example_hands = [
        " 4♥ 11♥  4♣ 10♥ 10♦",  # Two Pair
        " A♥  K♥  Q♥  J♥ 10♥",  # Straight Flush
        " 2♠  2♣  2♦  2♥  9♠",  # Four of a Kind
        " 5♠  5♣  5♦  9♥  9♠",  # Full House
        " 2♠  5♠  9♠  J♠  K♠",  # Flush
        " 6♥  7♣  8♦  9♠ 10♥",  # Straight
        " A♠  2♣  3♦  4♥  5♠",  # Straight (wheel)
        " 3♠  3♣  3♦  7♥  9♠",  # Three of a Kind
        " 4♠  4♣  9♦  9♥  2♠",  # Two Pair
        " 8♠  8♣  2♦  5♥  9♠",  # One Pair
        " 2♠  5♣  9♦  J♥  K♠",  # High Card
    ]

    for hand in example_hands:
        name = classify_hand(hand)
        readable = format_hand(hand)
        print(hand + " -> " + name + " (" + readable + ")")


if __name__ == "__main__":
    main()
