import asyncio, logging, random, math, uuid
from collections import deque
from typing import Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("nexus")


class OUSimulator:
    """Mean-reverting Ornstein-Uhlenbeck price process."""
    def __init__(self):
        self._prices = {}
        self._mu = {}
        self._theta = {}
        self._sigma = {}
        self._trend = {}
        self._hist = {}
        self._tick = 0
        self._init()

    def _init(self):
        syms = {
            "DOGE/USDT":0.15,"SHIB/USDT":0.000025,"PEPE/USDT":0.000012,
            "ARB/USDT":1.15,"OP/USDT":2.80,"SUI/USDT":3.50,"APT/USDT":8.50,
            "NEAR/USDT":5.20,"FIL/USDT":5.80,"AVAX/USDT":35.0,"MATIC/USDT":0.72,
            "LINK/USDT":14.5,"ATOM/USDT":9.0,"DOT/USDT":7.2,"ADA/USDT":0.45,
            "SOL/USDT":145.0,"XRP/USDT":0.52,"LTC/USDT":85.0,"UNI/USDT":7.5,
            "AAVE/USDT":95.0,"INJ/USDT":22.0,"TIA/USDT":11.0,"SEI/USDT":0.45,
            "JUP/USDT":0.85,"WIF/USDT":2.30,"BONK/USDT":0.00002,"FET/USDT":2.10,
            "RNDR/USDT":9.50,"GRT/USDT":0.28,
        }
        for s, p in syms.items():
            self._prices[s] = p
            self._mu[s] = p
            self._theta[s] = random.uniform(0.02, 0.08)
            self._sigma[s] = p * random.uniform(0.008, 0.025)
            self._trend[s] = 0
            self._hist[s] = deque(maxlen=300)

    def tick(self):
        self._tick += 1
        for s in self._prices:
            theta = self._theta[s]
            mu = self._mu[s]
            sigma = self._sigma[s]
            x = self._prices[s]
            dr = theta * (mu - x) / x
            shock = sigma / x * random.gauss(0, 1)
            if random.random() < 0.008:
                shock += random.choice([1, -1]) * random.uniform(0.01, 0.04)
            if random.random() < 0.005:
                self._trend[s] = random.uniform(-0.002, 0.002)
            self._mu[s] *= (1 + self._trend[s])
            self._mu[s] = max(self._mu[s], 1e-10)
            if random.random() < 0.01:
                sigma *= random.uniform(1.5, 3.0)
            ret = dr + shock
            self._prices[s] *= (1 + ret)
            self._prices[s] = max(self._prices[s], 1e-10)
            self._hist[s].append(self._prices[s])

    def get(self, s):
        return self._prices.get(s, 0)

    def hist(self, s, n=60):
        return list(self._hist.get(s, []))[-n:]

    def tickers(self):
        t = {}
        for s, p in self._prices.items():
            sp = p * 0.0004
            t[s] = {"last": p, "bid": p-sp, "ask": p+sp,
                    "vol": random.uniform(500000, 20000000)}
        return t


def rsi(c, p=14):
    if len(c) < p+1: return 50.0
    d = [c[i]-c[i-1] for i in range(1, len(c))]
    g = [max(x, 0) for x in d]
    l = [max(-x, 0) for x in d]
    ag = sum(g[:p])/p
    al = sum(l[:p])/p
    for i in range(p, len(g)):
        ag = (ag*(p-1)+g[i])/p
        al = (al*(p-1)+l[i])/p
    return 100-(100/(1+ag/al)) if al > 0 else 100.0


def ema(data, p):
    if len(data) < p: return None
    k = 2/(p+1)
    e = sum(data[:p])/p
    for v in data[p:]:
        e = v*k+e*(1-k)
    return e


def bb(c, p=20):
    if len(c) < p: return None, None, None
    w = c[-p:]
    m = sum(w)/p
    s = (sum((x-m)**2 for x in w)/p)**0.5
    return m, m+2*s, m-2*s


class Engine:
    def __init__(self):
        self._m = OUSimulator()
        self.cfg = {
            "lev": 5, "pos": 0.10, "fee": 0.0018,
            "rsi_buy": 33, "rsi_sell": 67,
            "tp": 0.8, "sl": 3.5,
            "bb_tp": 0.7, "bb_sl": 3.0,
            "vwap_tp": 0.6, "vwap_sl": 3.0, "vwap_dev": 1.0,
            "mom_tp": 1.0, "mom_sl": 2.5, "mom_thr": 1.5,
        }
        self._ot = {}
        self._dl = 0
        self._cl = 0
        self._cd = 0
        self._t = 0
        self._cap = 100.0
        self._peak = 100.0
        self._mdd = 0.0
        self._pnl = 0.0
        self._w = 0
        self._l = 0
        self._ss = 0
        self._so = 0
        self._bs = {}

    async def run(self, dur=21600):
        log.info("=" * 60)
        log.info("  ALTCOIN NEXUS - Mean Reversion Engine (OU Model)")
        log.info("  $100 | Lev %dx | TP %.1f%% | SL %.1f%%" % (self.cfg["lev"], self.cfg["tp"], self.cfg["sl"]))
        log.info("  4 strategies | %d ticks" % dur)
        log.info("=" * 60)
        warmup = 40
        scan_iv = 5
        for t in range(dur):
            self._t = t
            self._m.tick()
            await self._manage()
            if t > warmup and t % scan_iv == 0:
                await self._scan()
            if t % 2000 == 0 and t > 0:
                self._status()
            if t % 500 == 0:
                await asyncio.sleep(0)
        self._report()

    async def _scan(self):
        tk = self._m.tickers()
        open_syms = {tr["sym"] for tr in self._ot.values()}
        sigs = []
        for sym, t in tk.items():
            if sym in open_syms:
                continue
            p = t["last"]
            if t["vol"] < 500000 or p > 500 or p < 0.0001:
                continue
            cl = self._m.hist(sym, 60)
            if len(cl) < 25:
                continue
            r = rsi(cl, 14)
            ma, bu, bl = bb(cl, 20)
            ef = ema(cl, 5)
            es = ema(cl, 13)
            vwap = sum(cl[-20:])/20 if len(cl) >= 20 else None
            dev = (p-vwap)/vwap*100 if vwap else 0

            if r < self.cfg["rsi_buy"]:
                sigs.append({"sym":sym,"dir":"LONG","strat":"rsi_mr","p":p,"r":r,
                             "sc":90+(self.cfg["rsi_buy"]-r),"tp":self.cfg["tp"],"sl":self.cfg["sl"]})
            elif r > self.cfg["rsi_sell"]:
                sigs.append({"sym":sym,"dir":"SHORT","strat":"rsi_mr","p":p,"r":r,
                             "sc":90+(r-self.cfg["rsi_sell"]),"tp":self.cfg["tp"],"sl":self.cfg["sl"]})

            if ma and bu and bl and (bu-bl)/ma*100 > 0.5:
                if p <= bl and r < 40:
                    sigs.append({"sym":sym,"dir":"LONG","strat":"bb","p":p,"r":r,"sc":82,
                                 "tp":self.cfg["bb_tp"],"sl":self.cfg["bb_sl"]})
                elif p >= bu and r > 60:
                    sigs.append({"sym":sym,"dir":"SHORT","strat":"bb","p":p,"r":r,"sc":82,
                                 "tp":self.cfg["bb_tp"],"sl":self.cfg["bb_sl"]})

            if vwap and abs(dev) > self.cfg["vwap_dev"]:
                d = "LONG" if dev < 0 else "SHORT"
                sigs.append({"sym":sym,"dir":d,"strat":"vwap","p":p,"r":r,"sc":78,
                             "tp":self.cfg["vwap_tp"],"sl":self.cfg["vwap_sl"]})

            if len(cl) >= 10:
                mom = (sum(cl[-5:])/5 - sum(cl[-10:-5])/5) / (sum(cl[-10:-5])/5) * 100
                if mom > self.cfg["mom_thr"] and ef and es and ef > es and 40 < r < 75:
                    sigs.append({"sym":sym,"dir":"LONG","strat":"mom","p":p,"r":r,"sc":75,
                                 "tp":self.cfg["mom_tp"],"sl":self.cfg["mom_sl"]})
                elif mom < -self.cfg["mom_thr"] and ef and es and ef < es and 25 < r < 60:
                    sigs.append({"sym":sym,"dir":"SHORT","strat":"mom","p":p,"r":r,"sc":75,
                                 "tp":self.cfg["mom_tp"],"sl":self.cfg["mom_sl"]})

        sigs.sort(key=lambda s: s["sc"], reverse=True)
        self._ss += len(sigs)
        mx = min(3, 10 - len(self._ot))
        for s in sigs[:mx]:
            if self._t < self._cd:
                break
            if self._dl >= self._cap * 0.35:
                break
            if self._cap < 3:
                break
            await self._open(s)

    async def _open(self, sig):
        sym = sig["sym"]
        p = sig["p"]
        d = sig["dir"]
        stk = max(self._cap * self.cfg["pos"], 0.5)
        lev = self.cfg["lev"]
        tp = sig["tp"]
        sl = sig["sl"]
        st = sig["strat"]
        if d == "LONG":
            tpp = p*(1+tp/100)
            slp = p*(1-sl/100)
        else:
            tpp = p*(1-tp/100)
            slp = p*(1+sl/100)
        tid = "t_" + uuid.uuid4().hex[:8]
        self._ot[tid] = {"id":tid,"sym":sym,"dir":d,"strat":st,"ep":p,"stk":stk,"lev":lev,
                         "tp":tp,"sl":sl,"tpp":tpp,"slp":slp,"tp1":False,"bp":p,"ot":self._t}
        self._so += 1
        if st not in self._bs:
            self._bs[st] = {"w":0,"l":0,"pnl":0}
        log.info("  OPEN  %12s %5s @%.6f TP=%.1f%% SL=%.1f%% $%.2fx%d rsi=%.1f [%s]" % (sym,d,p,tp,sl,stk,lev,sig.get("r",0),st))

    async def _manage(self):
        rm = []
        for tid, tr in list(self._ot.items()):
            cp = self._m.get(tr["sym"])
            if not cp:
                continue
            ep = tr["ep"]
            d = tr["dir"]
            lev = tr["lev"]
            stk = tr["stk"]
            if d == "LONG":
                pp = (cp-ep)/ep*100
                tr["bp"] = max(tr["bp"], cp)
            else:
                pp = (ep-cp)/ep*100
                tr["bp"] = min(tr["bp"], cp)
            net = pp*lev/100 - self.cfg["fee"]

            if not tr["tp1"] and pp >= tr["tp"]:
                tr["tp1"] = True
                pnl = stk*0.5*net
                self._cap += pnl
                self._pnl += pnl
                self._w += 1
                self._cl = 0
                self._bs[tr["strat"]]["w"] += 1
                self._bs[tr["strat"]]["pnl"] += pnl
                log.info("  TP1   %12s %5s pp=%+.2f%% $%+.2f cap=$%.2f" % (tr["sym"],d,pp,pnl,self._cap))

            if pp <= -tr["sl"]:
                pnl = stk*net
                await self._close(tid, pnl, cp, "stop")
                rm.append(tid)
                continue

            if tr["tp1"] and pp >= tr["tp"]*2.5:
                pnl = stk*0.5*net
                await self._close(tid, pnl, cp, "tp2")
                rm.append(tid)
                continue

            if tr["tp1"]:
                bp = tr["bp"]
                retr = (bp-cp)/bp*100 if d == "LONG" else (cp-bp)/bp*100
                if retr > 0.3 and pp > 0:
                    pnl = stk*0.5*net
                    await self._close(tid, pnl, cp, "trail")
                    rm.append(tid)
                    continue

            if self._t - tr["ot"] > 500:
                m = 0.5 if tr["tp1"] else 1.0
                pnl = stk*m*net
                await self._close(tid, pnl, cp, "expire")
                rm.append(tid)
                continue

        for tid in rm:
            self._ot.pop(tid, None)

    async def _close(self, tid, pnl, cp, reason):
        tr = self._ot.get(tid)
        if not tr:
            return
        self._cap += pnl
        self._pnl += pnl
        self._peak = max(self._peak, self._cap)
        dd = (self._peak-self._cap)/max(self._peak, 0.01)*100
        self._mdd = max(self._mdd, dd)
        st = tr["strat"]
        if pnl >= 0:
            self._w += 1
            self._cl = 0
            self._bs[st]["w"] += 1
        else:
            self._l += 1
            self._cl += 1
            self._dl += abs(pnl)
            self._bs[st]["l"] += 1
            if self._cl >= 5:
                self._cd = self._t + 20
                self._cl = 0
                log.warning("  COOLDOWN: 5 consec losses")
        self._bs[st]["pnl"] += pnl
        ep = tr["ep"]
        d = tr["dir"]
        pp = (cp-ep)/ep*100 if d == "LONG" else (ep-cp)/ep*100
        sign = "+" if pnl >= 0 else ""
        log.info("  CLOSE %12s %5s e=%.6f x=%.6f pnl=$%s%.2f (%+.2f%%) %s cap=$%.2f" % (tr["sym"],d,ep,cp,sign,pnl,pp,reason,self._cap))

    def _status(self):
        t = self._w+self._l
        wr = self._w/max(t, 1)*100
        log.info("-" * 60)
        log.info("  t=%d cap=$%.2f pnl=$%+.2f wr=%.1f%% trades=%d(%dW/%dL) open=%d dd=%.1f%%" % (self._t,self._cap,self._pnl,wr,t,self._w,self._l,len(self._ot),self._mdd))
        for st, d in sorted(self._bs.items()):
            tw = d["w"]+d["l"]
            sw = d["w"]/max(tw, 1)*100
            log.info("    %8s: %3d %5.1f%%WR $%+.2f" % (st,tw,sw,d["pnl"]))
        log.info("-" * 60)

    def _report(self):
        t = self._w+self._l
        wr = self._w/max(t, 1)*100
        ret = (self._cap-100)/100*100
        log.info("")
        log.info("=" * 60)
        log.info("  FINAL REPORT")
        log.info("=" * 60)
        log.info("  Starting Capital:  $100.00")
        log.info("  Final Capital:     $%.2f" % self._cap)
        log.info("  Total Return:      %+.1f%%" % ret)
        log.info("  Total PnL:         $%+.2f" % self._pnl)
        log.info("  Win Rate:          %.1f%% (%dW / %dL)" % (wr, self._w, self._l))
        log.info("  Total Trades:      %d" % t)
        log.info("  Max Drawdown:      %.1f%%" % self._mdd)
        log.info("  Peak Capital:      $%.2f" % self._peak)
        log.info("  Signals Scanned:   %d" % self._ss)
        log.info("  Ticks:             %d" % self._t)
        log.info("")
        log.info("  STRATEGY BREAKDOWN:")
        for st, d in sorted(self._bs.items()):
            tw = d["w"]+d["l"]
            sw = d["w"]/max(tw, 1)*100
            log.info("    %8s: %3d trades | %5.1f%% WR | $%+.2f" % (st,tw,sw,d["pnl"]))
        log.info("=" * 60)
        if wr >= 80:
            log.info("  >>> WIN RATE TARGET: >= 80%% <<<")
        else:
            log.info("  >>> Win Rate %.1f%% <<<" % wr)
        if self._cap >= 200:
            log.info("  >>> CAPITAL DOUBLED: $100 -> $%.2f <<<" % self._cap)
        log.info("=" * 60)


async def main():
    log.info("Starting Altcoin Nexus (OU mean-reverting engine)...")
    await Engine().run(21600)

if __name__ == "__main__":
    asyncio.run(main())
