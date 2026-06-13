def compute(items):
    total = 0.0
    for item in items:
        price = float(item["price"])
        qty = int(item["quantity"])
        line = price * qty
        if qty > 10:
            line = line * 0.9
        total = total + line
    tax = total * 0.19
    return total + tax
