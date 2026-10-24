fun compute(items: List<Int>): Int {
    var total = 0
    for (item in items) {
        val price = item * 3
        val quantity = item + 2
        var line = price * quantity
        if (quantity > 10) {
            line = line * 9 / 10
        }
        total += line
    }
    val tax = total * 19 / 100
    return total + tax
}
