"""
Anything with resources goes here
"""
import logging
import re
import time
import json
from core.extractors import Extractor
from game.market import PremiumExchange


class ResourceManager:
    """
    Class to calculate, store and reserve resources for actions
    Optimized for smart premium trading
    """
    actual = {}

    requested = {}

    storage = 0
    ratio = 2.0  # Verkauft ab 50% Storage (früher und aggressiver)
    max_trade_amount = 4000
    logger = None
    # not allowed to bias
    trade_bias = 1
    last_trade = 0
    trade_max_per_hour = 1
    trade_max_duration = 2
    wrapper = None
    village_id = None
    do_premium_trade = False
    last_troop_recruit_time = 0

    def __init__(self, wrapper=None, village_id=None):
        """
        Create the resource manager
        Preferably used by anything that builds/recruits/sends/whatever
        """
        self.wrapper = wrapper
        self.village_id = village_id

    def update(self, game_state):
        """
        Update the current resources based on the game state
        """
        self.actual["wood"] = game_state["village"]["wood"]
        self.actual["stone"] = game_state["village"]["stone"]
        self.actual["iron"] = game_state["village"]["iron"]
        self.actual["pop"] = (
                game_state["village"]["pop_max"] - game_state["village"]["pop"]
        )
        self.storage = game_state["village"]["storage_max"]
        self.check_state()
        store_state = game_state["village"]["name"]
        self.logger = logging.getLogger(f"Resource Manager: {store_state}")

    def do_premium_stuff(self):
        """
        Smart Premium Exchange: Verkauft Ressourcen-Überschuss for Premium-Punkte
        """
        if not self.do_premium_trade:
            return

        def _format_pp(value: float) -> str:
            rounded = round(value, 2)
            if abs(rounded - round(rounded)) < 1e-6:
                return str(int(round(rounded)))
            return f"{rounded:.2f}"

        gpl = self.get_plenty_off()
        if not gpl:
            return

        url = f"game.php?village={self.village_id}&screen=market&mode=exchange"
        res = self.wrapper.get_url(url=url)
        data = Extractor.premium_data(res.text)

        if not data or data["merchants"] < 1:
            return

        try:
            premium_exchange = PremiumExchange(
                wrapper=self.wrapper,
                stock=data["stock"],
                capacity=data["capacity"],
                tax=data["tax"],
                constants=data["constants"],
                duration=data["duration"],
                merchants=data["merchants"]
            )
            cost_per_point = premium_exchange.calculate_rate_for_one_point(gpl)
        except Exception as e:
            self.logger.warning(f"[Premium] Error calculating exchange rate: {e}")
            return

        threshold = int(self.storage / self.ratio)
        current_amount = self.actual.get(gpl, 0)
        requested_amount = self.in_need_amount(gpl)
        available_surplus = max(0, current_amount - threshold - requested_amount)

        if available_surplus <= 0:
            return

        gpl_data = PremiumExchange.optimize_n(
            amount=available_surplus,
            sell_price=cost_per_point,
            merchants=data["merchants"],
            size=1000
        )

        sell_amount = gpl_data.get("sell_amount", 0)
        if sell_amount < 1 or gpl_data["ratio"] > 0.45:
            return

        try:
            estimated_pp = abs(premium_exchange.calculate_cost(gpl, -sell_amount))
        except ValueError:
            return

        if estimated_pp < 1:
            return

        result = self.wrapper.get_api_action(
            self.village_id,
            action="exchange_begin",
            params={"screen": "market"},
            data={f"sell_{gpl}": sell_amount},
        )

        if not result:
            return

        try:
            _rate_hash = result["response"][0]["rate_hash"]
        except (KeyError, IndexError):
            return

        trade_data = {f"sell_{gpl}": sell_amount, "rate_hash": _rate_hash, "mb": "1"}
        result = self.wrapper.get_api_action(
            self.village_id,
            action="exchange_confirm",
            params={"screen": "market"},
            data=trade_data,
        )

        if result:
            self.logger.info(f"[Premium] Trade successful! Sold {sell_amount} {gpl}")
            self.wrapper.reporter.report(
                self.village_id,
                "TWB_PREMIUM_TRADE",
                f"Sold {sell_amount} {gpl} for premium points"
            )

    def check_state(self):
        for source in self.requested:
            for res in self.requested[source]:
                if self.requested[source][res] <= self.actual[res]:
                    self.requested[source][res] = 0

    def mark_troop_recruited(self):
        self.last_troop_recruit_time = int(time.time())

    def can_build(self, prioritize_troops, timeout):
        if not prioritize_troops or self.last_troop_recruit_time == 0:
            return True
        active_recruitment = any(sum(self.requested[k].values()) > 0 for k in self.requested if k.startswith("recruitment_"))
        if not active_recruitment:
            return True
        elapsed = int(time.time()) - self.last_troop_recruit_time
        return elapsed >= timeout

    def request(self, source="building", resource="wood", amount=1):
        if source in self.requested:
            self.requested[source][resource] = amount
        else:
            self.requested[source] = {resource: amount}

    def can_recruit(self):
        if self.actual["pop"] == 0:
            to_del = [x for x in self.requested if "recruitment" in x]
            for x in to_del:
                del self.requested[x]
            return False
        return not any(any(v > 0 for v in self.requested[x].values()) for x in self.requested if "recruitment" not in x)

    def get_plenty_off(self):
        most_of, most = 0, None
        for sub in self.actual:
            if sub == "pop" or any(sub in self.requested[sr] and self.requested[sr][sub] > 0 for sr in self.requested):
                continue
            if self.actual[sub] > int(self.storage / self.ratio):
                if self.actual[sub] > most_of:
                    most, most_of = sub, self.actual[sub]
        return most

    def in_need_of(self, obj_type):
        return any(obj_type in self.requested[x] and self.requested[x][obj_type] > 0 for x in self.requested)

    def in_need_amount(self, obj_type):
        return sum(self.requested[x].get(obj_type, 0) for x in self.requested if self.requested[x].get(obj_type, 0) > 0)

    def get_needs(self):
        needed_the_most, needed_amount = None, 0
        for x in self.requested:
            for obj_type, amount in self.requested[x].items():
                if amount > needed_amount:
                    needed_amount, needed_the_most = amount, obj_type
        return (needed_the_most, needed_amount) if needed_the_most else None

    def trade(self, me_item, me_amount, get_item, get_amount):
        url = f"game.php?village={self.village_id}&screen=market&mode=own_offer"
        res = self.wrapper.get_url(url=url)
        if 'market_merchant_available_count">0' in res.text:
            return False
        payload = {
            "res_sell": me_item, "sell": me_amount, "res_buy": get_item, "buy": get_amount,
            "max_time": self.trade_max_duration, "multi": 1, "h": self.wrapper.last_h,
        }
        self.wrapper.post_url(f"game.php?village={self.village_id}&screen=market&mode=own_offer&action=new_offer", data=payload)
        self.last_trade = int(time.time())
        return True

    def drop_existing_trades(self):
        url = f"game.php?village={self.village_id}&screen=market&mode=all_own_offer"
        data = self.wrapper.get_url(url)
        existing = re.findall(r'data-id="(\d+)".+?data-village="(\d+)"', data.text)
        for offer, village in existing:
            if village == str(self.village_id):
                post_url = f"game.php?village={self.village_id}&screen=market&mode=all_own_offer&action=delete_offers"
                self.wrapper.post_url(post_url, data={"id_%s" % offer: "on", "delete": "Verwijderen", "h": self.wrapper.last_h})

    def readable_ts(self, seconds):
        seconds = (seconds - int(time.time())) % (24 * 3600)
        return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)

    def manage_market(self, drop_existing=True):
        if self.last_trade + int(3600 * self.trade_max_per_hour) > int(time.time()) or time.localtime().tm_hour in (23, 0, 1, 2, 3, 4, 5):
            return
        if drop_existing:
            self.drop_existing_trades()
        plenty = self.get_plenty_off()
        if plenty and not self.in_need_of(plenty):
            need = self.get_needs()
            if not need: return
            item, how_many = need
            how_many = round(how_many, -1)
            if how_many < 250: return
            if self.check_other_offers(item, how_many, plenty): return
            if how_many > self.max_trade_amount: how_many = self.max_trade_amount
            biased = int(how_many * self.trade_bias)
            if self.actual[plenty] >= biased:
                self.trade(plenty, biased, item, how_many)

    def check_other_offers(self, item, how_many, sell):
        url = f"game.php?village={self.village_id}&screen=market&mode=other_offer"
        res = self.wrapper.get_url(url=url)
        cur_off_tds = re.findall(r"(?:<!-- insert the offer -->\n+)\s+<tr>(.*?)<\/tr>", res.text, re.S | re.M)
        willing_to_sell = self.actual[sell] - self.in_need_amount(sell)
        for tds in cur_off_tds:
            res_offer = re.findall(r"<span class=\"icon header (.+?)\".+?>(.+?)</td>", tds)
            off_id = re.findall(r"<input type=\"hidden\" name=\"id\" value=\"(\d+)", tds)
            if not off_id: continue
            offer = self.parse_res_offer(res_offer, off_id[0])
            if offer["offered"] == item and offer["offer_amount"] >= how_many and offer["wanted"] == sell and offer["wanted_amount"] <= willing_to_sell:
                payload = {"count": 1, "id": offer["id"], "h": self.wrapper.last_h}
                self.wrapper.post_url(f"game.php?village={self.village_id}&screen=market&mode=other_offer&action=accept_multi&start=0&id={offer['id']}&h={self.wrapper.last_h}", data=payload)
                self.last_trade = int(time.time())
                self.actual[offer["wanted"]] -= offer["wanted_amount"]
                return True
        return False

    def parse_res_offer(self, res_offer, id):
        off, want, _ = res_offer
        return {
            "id": id, "offered": off[0], "offer_amount": int("".join(filter(str.isdigit, off[1]))),
            "wanted": want[0], "wanted_amount": int("".join(filter(str.isdigit, want[1])))
        }
