<?php

class SampleA
{
    public function calculate(array $items): float
    {
        $total = 0.0;
        foreach ($items as $item) {
            $price = (float) $item['price'];
            $qty = (int) $item['quantity'];
            $line = $price * $qty;
            if ($qty > 10) {
                $line = $line * 0.9;
            }
            $total = $total + $line;
        }
        $tax = $total * 0.19;
        return $total + $tax;
    }
}
