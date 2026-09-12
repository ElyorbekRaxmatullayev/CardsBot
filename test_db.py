from database import get_or_create_user, get_user_data, add_new_card_to_db, get_all_cards

# Test basic user
get_or_create_user(12345, "testuser", "Test")
user = get_user_data(12345)
print("User:", user)

# Test cards
add_new_card_to_db({
    "name": "Test Card",
    "rarity": "Common",
    "attack": 100,
    "hp": 200,
    "value": 10
})
cards = get_all_cards()
print("Cards:", cards)

print("SUCCESS!")
