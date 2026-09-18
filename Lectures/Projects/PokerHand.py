# Poker hand classifier
#
# Each card is a 4-character string:
#   characters 0-1: the value, right-justified ( " 4", " K", " A", "11", "10")
#   character 2: the suit, one of the characters in "♠♣♥♦"
#   character 3: a trailing separator space
#
# Example hand (two pair): " 4♥ 11♥  4♣ 10♥ 10♦"
#
# This program only uses if statements, input, output (print), string
# operations, and mathematical operations. No functions are defined.

hand = input("Enter a 5-card hand (5 cards, 4 characters each): ")

# The trailing separator on the final card is optional.
if len(hand) == 19:
    hand = hand + " "

card1 = hand[0:4]
card2 = hand[4:8]
card3 = hand[8:12]
card4 = hand[12:16]
card5 = hand[16:20]

# --- Parse each card's value ---

text1 = card1[0] + card1[1]
if text1 == " A":
    value1 = 14
elif text1 == " K":
    value1 = 13
elif text1 == " Q":
    value1 = 12
elif text1 == " J":
    value1 = 11
else:
    value1 = int(text1)

text2 = card2[0] + card2[1]
if text2 == " A":
    value2 = 14
elif text2 == " K":
    value2 = 13
elif text2 == " Q":
    value2 = 12
elif text2 == " J":
    value2 = 11
else:
    value2 = int(text2)

text3 = card3[0] + card3[1]
if text3 == " A":
    value3 = 14
elif text3 == " K":
    value3 = 13
elif text3 == " Q":
    value3 = 12
elif text3 == " J":
    value3 = 11
else:
    value3 = int(text3)

text4 = card4[0] + card4[1]
if text4 == " A":
    value4 = 14
elif text4 == " K":
    value4 = 13
elif text4 == " Q":
    value4 = 12
elif text4 == " J":
    value4 = 11
else:
    value4 = int(text4)

text5 = card5[0] + card5[1]
if text5 == " A":
    value5 = 14
elif text5 == " K":
    value5 = 13
elif text5 == " Q":
    value5 = 12
elif text5 == " J":
    value5 = 11
else:
    value5 = int(text5)

# --- Parse each card's suit ---

suit1 = card1[2]
suit2 = card2[2]
suit3 = card3[2]
suit4 = card4[2]
suit5 = card5[2]

# --- Check for a flush (all five suits match) ---

is_flush = True
if suit1 != suit2:
    is_flush = False
if suit1 != suit3:
    is_flush = False
if suit1 != suit4:
    is_flush = False
if suit1 != suit5:
    is_flush = False

# --- Sort the five values from low to high (bubble sort) ---

s1 = value1
s2 = value2
s3 = value3
s4 = value4
s5 = value5

if s1 > s2:
    temp = s1
    s1 = s2
    s2 = temp
if s2 > s3:
    temp = s2
    s2 = s3
    s3 = temp
if s3 > s4:
    temp = s3
    s3 = s4
    s4 = temp
if s4 > s5:
    temp = s4
    s4 = s5
    s5 = temp

if s1 > s2:
    temp = s1
    s1 = s2
    s2 = temp
if s2 > s3:
    temp = s2
    s2 = s3
    s3 = temp
if s3 > s4:
    temp = s3
    s3 = s4
    s4 = temp

if s1 > s2:
    temp = s1
    s1 = s2
    s2 = temp
if s2 > s3:
    temp = s2
    s2 = s3
    s3 = temp

if s1 > s2:
    temp = s1
    s1 = s2
    s2 = temp

# --- Check for a straight (5 consecutive values, sorted) ---

is_straight = False
if s2 - s1 == 1 and s3 - s2 == 1 and s4 - s3 == 1 and s5 - s4 == 1:
    is_straight = True

# Ace-2-3-4-5 ("the wheel") also counts as a straight.
if s1 == 2 and s2 == 3 and s3 == 4 and s4 == 5 and s5 == 14:
    is_straight = True

# --- Count how many times each distinct value appears ---

count1 = 0
if value1 == s1:
    count1 = count1 + 1
if value2 == s1:
    count1 = count1 + 1
if value3 == s1:
    count1 = count1 + 1
if value4 == s1:
    count1 = count1 + 1
if value5 == s1:
    count1 = count1 + 1

count2 = 0
if value1 == s2:
    count2 = count2 + 1
if value2 == s2:
    count2 = count2 + 1
if value3 == s2:
    count2 = count2 + 1
if value4 == s2:
    count2 = count2 + 1
if value5 == s2:
    count2 = count2 + 1

count3 = 0
if value1 == s3:
    count3 = count3 + 1
if value2 == s3:
    count3 = count3 + 1
if value3 == s3:
    count3 = count3 + 1
if value4 == s3:
    count3 = count3 + 1
if value5 == s3:
    count3 = count3 + 1

count4 = 0
if value1 == s4:
    count4 = count4 + 1
if value2 == s4:
    count4 = count4 + 1
if value3 == s4:
    count4 = count4 + 1
if value4 == s4:
    count4 = count4 + 1
if value5 == s4:
    count4 = count4 + 1

count5 = 0
if value1 == s5:
    count5 = count5 + 1
if value2 == s5:
    count5 = count5 + 1
if value3 == s5:
    count5 = count5 + 1
if value4 == s5:
    count5 = count5 + 1
if value5 == s5:
    count5 = count5 + 1

# --- Find the highest and second-highest counts ---

top_count = 0
if count1 > top_count:
    top_count = count1
if count2 > top_count:
    top_count = count2
if count3 > top_count:
    top_count = count3
if count4 > top_count:
    top_count = count4
if count5 > top_count:
    top_count = count5

second_count = 0
if count1 > second_count and count1 < top_count:
    second_count = count1
if count2 > second_count and count2 < top_count:
    second_count = count2
if count3 > second_count and count3 < top_count:
    second_count = count3
if count4 > second_count and count4 < top_count:
    second_count = count4
if count5 > second_count and count5 < top_count:
    second_count = count5

# A four-of-a-kind or a pair-plus-pair-of-something-else needs the second
# highest count computed among values that are NOT the top-count value.
# If two distinct values both reach top_count (e.g. two pair, or a full
# house's pair matching the triple check above), second_count as computed
# above only finds counts strictly less than top_count, so we also check
# for a second value that ties top_count.
tied_top = 0
if count1 == top_count:
    tied_top = tied_top + 1
if count2 == top_count and s2 != s1:
    tied_top = tied_top + 1
if count3 == top_count and s3 != s1 and s3 != s2:
    tied_top = tied_top + 1
if count4 == top_count and s4 != s1 and s4 != s2 and s4 != s3:
    tied_top = tied_top + 1
if count5 == top_count and s5 != s1 and s5 != s2 and s5 != s3 and s5 != s4:
    tied_top = tied_top + 1

if tied_top >= 2 and top_count == 2:
    second_count = 2

# --- Classify the hand ---

if is_straight and is_flush:
    result = "Straight Flush"
elif top_count == 4:
    result = "Four of a Kind"
elif top_count == 3 and second_count == 2:
    result = "Full House"
elif is_flush:
    result = "Flush"
elif is_straight:
    result = "Straight"
elif top_count == 3:
    result = "Three of a Kind"
elif top_count == 2 and second_count == 2:
    result = "Two Pair"
elif top_count == 2:
    result = "One Pair"
else:
    result = "High Card"

print(result)
