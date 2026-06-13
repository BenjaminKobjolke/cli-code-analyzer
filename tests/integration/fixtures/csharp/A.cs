using System.Collections.Generic;

public class SampleA
{
    public double Calculate(List<Dictionary<string, object>> items)
    {
        double total = 0.0;
        foreach (var item in items)
        {
            double price = (double)item["price"];
            int qty = (int)item["quantity"];
            double line = price * qty;
            if (qty > 10)
            {
                line = line * 0.9;
            }
            total = total + line;
        }
        double tax = total * 0.19;
        return total + tax;
    }
}
