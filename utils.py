import random

def gamba(value: int) -> int:
    if random.random() < 0.45:
        return 2 * value
    else:
        return 0