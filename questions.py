import random


def generate_mathematics_question() -> str:
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    return f"{a} + {b}"

    
def generate_roman_numerals_question() -> str:
    number = random.randint(1, 3999)
    vals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
    ]
    roman = ""
    for (decimal_value, numeral) in vals:
        while number >= decimal_value:
            roman += numeral
            number -= decimal_value
    return roman

    
def generate_usable_addresses_question() -> str:
    subnets = ["192.168.1.0/24", "10.0.0.0/16", "172.16.0.0/20"]
    return random.choice(subnets)

    
def generate_network_broadcast_question() -> str:
    subnets = ["192.168.1.0/24", "10.0.0.0/16", "172.16.0.0/20"]
    return random.choice(subnets)
