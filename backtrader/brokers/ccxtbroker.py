#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015, 2016, 2017 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import collections
from backtrader.position import Position
from backtrader import BrokerBase, OrderBase, Order
from backtrader.utils.py3 import queue
from backtrader.stores.ccxtstore import CCXTStore

class CCXTOrder(OrderBase):
    def __init__(self, owner, data, ccxt_order):
        self.owner = owner
        self.data = data
        self.ccxt_order = ccxt_order
        self.ordtype = self.Buy if ccxt_order['side'] == 'buy' else self.Sell
        self.size = float(ccxt_order['amount'])

        super(CCXTOrder, self).__init__()

class CCXTBroker(BrokerBase):
    '''Broker implementation for CCXT cryptocurrency trading library.

    This class maps the orders/positions from CCXT to the
    internal API of ``backtrader``.
    '''

    order_types = {Order.Market: 'market',
                   Order.Limit: 'limit',
                   Order.Stop: 'stop',
                   Order.StopLimit: 'stop limit'}

    def __init__(self, exchange, currency, config, retries=5):
        super(CCXTBroker, self).__init__()

        self.store = CCXTStore(exchange, config, retries)

        self.currency = currency

        self.positions = collections.defaultdict(Position)

        self.notifs = queue.Queue()  # holds orders which are notified

        self.open_orders = list()

        self.startingcash = self.getcash()
        self.startingvalue = self.getvalue()

    def getcash(self):
        return self.store.getcash(self.currency)

    def getvalue(self, datas=None):
        return self.store.getvalue(self.currency)

    def get_notification(self):
        try:
            return self.notifs.get(False)
        except queue.Empty:
            return None

    def notify(self, order):
        self.notifs.put(order)

    def getposition(self, data, clone=True):
        currency = data.symbol.split('/')[0]
        return self.store.getposition(currency)
        # return self.o.getposition(data._dataname, clone=clone)
#         pos = self.positions[data._dataname]
#         if clone:
#             pos = pos.clone()
#
#         return pos

    def next(self):
        for o_order in list(self.open_orders):
            oID = o_order.ccxt_order['id']
            symbol = o_order.ccxt_order['symbol']
            ccxt_order = self.store.fetch_order(oID, symbol)
            if ccxt_order['status'] == 'closed':
#                 pos = self.getposition(o_order.data, clone=False)
#                 pos.update(o_order.size, o_order.price)
                o_order.completed()
                o_order.execute(float(ccxt_order['timestamp']),
                                ccxt_order['amount'],
                                ccxt_order['price'])
                self.notify(o_order)
                self.open_orders.remove(o_order)

    def _submit(self, owner, data, exectype, side, amount, price, params):
        order_type = self.order_types.get(exectype) if exectype else 'market'
        # Extract CCXT specific params if passed to the order
        params = params['params'] if 'params' in params else {}
        _order = self.store.create_order(symbol=data.symbol, order_type=order_type, side=side,
                                         amount=amount, price=price, params=params)

        order = CCXTOrder(owner, data, _order)
        order.submit()
        self.open_orders.append(order)
        #pos = self.getposition(data, clone=False)
        #pos.update(order.size, order.price)

#         self.notify(order)
        return order

    def buy(self, owner, data, size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None,
            **kwargs):
        return self._submit(owner, data, exectype, 'buy', size, price, kwargs)

    def sell(self, owner, data, size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None,
             **kwargs):
        return self._submit(owner, data, exectype, 'sell', size, price, kwargs)

    def cancel(self, order):
        oID = order.ccxt_order['id']
        symbol = order.ccxt_order['symbol']
        # check first if the order has already been filled otherwise an error
        # might be raised if we try to cancel an order that is not open.
        ccxt_order = self.store.fetch_order(oID, symbol)
        if ccxt_order['status'] == 'closed':
            return order

        ccxt_order = self.store.cancel_order(oID, symbol)
        self.open_orders.remove(order)
        order.cancel()
        self.notify(order)
        return order

    def get_orders_open(self, safe=False, symbol=None):
        for o_order in list(self.open_orders):
            oID = o_order.ccxt_order['id']
            symbol = o_order.ccxt_order['symbol']
            ccxt_order = self.store.fetch_order(oID, symbol)
            if ccxt_order['status'] == 'closed' or ccxt_order['status'] == 'canceled':
                self.open_orders.remove(o_order)
        return self.open_orders
#         return self.store.fetch_open_orders(symbol)
