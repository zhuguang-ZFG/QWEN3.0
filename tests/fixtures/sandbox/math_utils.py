"""A simple math utility for sandbox testing. No secrets, no network."""


def add(a: float, b: float) -> float:
    return a + b


def multiply(a: float, b: float) -> float:
    return a * b


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        a, b = float(sys.argv[1]), float(sys.argv[2])
        print(f"add({a}, {b}) = {add(a, b)}")
        print(f"multiply({a}, {b}) = {multiply(a, b)}")
    else:
        print("Usage: python math_utils.py <a> <b>")
