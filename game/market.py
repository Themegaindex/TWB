import logging
import re
import time
from core.extractors import Extractor

class PremiumExchange:
    """
    Optimized logic for interaction with the premium exchange
    Performance improvements: Binary Search, Error-Handling
    """

    def __init__(self, wrapper, stock: dict, capacity: dict, tax: dict, constants: dict, duration: int, merchants: int):
        self.wrapper = wrapper
        self.stock = stock
        self.capacity = capacity
        self.tax = tax
        self.constants = constants
        self.duration = duration
        self.merchants = merchants

    def calculate_cost(self, item, amount):
        if item not in self.stock or item not in self.capacity:
            raise ValueError(f"Invalid item: {item}")

        t = self.stock[item]
        n = self.capacity[item]

        if amount > 0 and t - amount < 0:
            raise ValueError(f"Not enough stock to buy {amount} {item} (available: {t})")
        if amount < 0 and t - amount > n:
            raise ValueError(f"Cannot sell {abs(amount)} {item}: capacity exceeded ({n})")

        tax = self.tax.get("buy", 0.0) if amount >= 0 else self.tax.get("sell", 0.0)

        price_before = self.calculate_marginal_price(t, n)
        price_after = self.calculate_marginal_price(t - amount, n)

        return (1.0 + float(tax)) * (price_before + price_after) * amount / 2.0

    def calculate_marginal_price(self, e, a):
        c = self.constants
        denominator = a + c["stock_size_modifier"]

        if denominator == 0:
            raise ZeroDivisionError("Stock size modifier results in division by zero")

        return c["resource_base_price"] - c["resource_price_elasticity"] * e / denominator

    def calculate_rate_for_one_point(self, item: str):
        if item not in self.stock:
            raise ValueError(f"Item {item} not found in stock")

        max_amount = int(self.capacity[item] - self.stock[item])
        if max_amount <= 0:
            raise ValueError(f"No capacity available for selling {item}")

        target = 1.0
        high = 1

        try:
            cost = abs(self.calculate_cost(item, -high))
        except ValueError as exc:
            raise ValueError(f"Unable to evaluate premium exchange cost: {exc}")

        while cost < target and high < max_amount:
            high = min(max_amount, high * 2)
            try:
                cost = abs(self.calculate_cost(item, -high))
            except ValueError:
                break

        if cost < target:
            return high

        low = max(1, high // 2)
        best = high

        while low <= high:
            mid = max(1, (low + high) // 2)
            try:
                mid_cost = abs(self.calculate_cost(item, -mid))
            except ValueError:
                high = mid - 1
                continue

            if mid_cost >= target:
                best = mid
                high = mid - 1
            else:
                low = mid + 1

        return best

    @staticmethod
    def optimize_n(amount, sell_price, merchants, size=1000):
        if amount <= 0 or merchants <= 0:
            return {
                "merchants": 0,
                "ratio": 1.0,
                "sell_amount": 0
            }

        def _ratio(resources, merchant_count, capacity=1000):
            return ((capacity * merchant_count) - resources) / capacity

        best_offer = None

        for used_merchants in range(1, merchants + 1):
            capacity = used_merchants * size
            sell_amount = min(amount, capacity)

            if sell_amount <= 0:
                continue

            ratio = _ratio(sell_amount, used_merchants, capacity=size)

            if ratio < 0:
                continue

            if best_offer is None:
                best_offer = (used_merchants, ratio, sell_amount)
                continue

            best_ratio = best_offer[1]

            if ratio < best_ratio or (abs(ratio - best_ratio) < 1e-9 and used_merchants > best_offer[0]):
                best_offer = (used_merchants, ratio, sell_amount)

        if best_offer is None:
            return {
                "merchants": 0,
                "ratio": 1.0,
                "sell_amount": 0
            }

        return {
            "merchants": best_offer[0],
            "ratio": best_offer[1],
            "sell_amount": best_offer[2]
        }
