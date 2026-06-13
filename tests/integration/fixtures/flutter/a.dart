class SampleA {
  double calculate(List<Map<String, dynamic>> items) {
    double total = 0.0;
    for (final item in items) {
      final price = item['price'] as double;
      final qty = item['quantity'] as int;
      var line = price * qty;
      if (qty > 10) {
        line = line * 0.9;
      }
      total = total + line;
    }
    final tax = total * 0.19;
    return total + tax;
  }
}
