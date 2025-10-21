import random


def generate_mathematics_question() -> str:
    operators = ["+", "-"]
    number_of_terms = random.randint(2, 5)
    expression = str(random.randint(1, 100))

    for _ in range(number_of_terms - 1):
        op = random.choice(operators)
        num = random.randint(1, 100)
        expression += f" {op} {num}"

    return expression

    
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
    prefix = random.randint(1, 32)
    ip = ".".join(str(random.randint(0, 255)) for _ in range(4))
    return f"{ip}/{prefix}"

    
def generate_network_broadcast_question() -> str:
    return generate_usable_addresses_question()  # both functions have same functionality
