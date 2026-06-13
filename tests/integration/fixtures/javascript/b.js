function compute(items) {
    let total = 0.0;
    for (const item of items) {
        const price = Number(item.price);
        const qty = Number(item.quantity);
        let line = price * qty;
        if (qty > 10) {
            line = line * 0.9;
        }
        total = total + line;
    }
    const tax = total * 0.19;
    return total + tax;
}

module.exports = { compute };
