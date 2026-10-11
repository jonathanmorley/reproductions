"""Repro: MKL VML sqrt SIGILLs Adam on pre-AVX2 Intel (torch CPU).

Trains a small word+char BiLSTM tagger with torch.optim.Adam on
synthetic data (built in — no downloads, no corpus). On affected
hardware (pre-AVX2 Intel + MKL builds that dispatch the `Z0HAynn`
single-precision VML sqrt variant) the run dies with SIGILL inside
`mkl_vml_kernel_sSqrt`, reached via `exp_avg_sq.sqrt()` in Adam's
single-tensor path:

    torch/optim/adam.py, _single_tensor_adam:  denom = (exp_avg_sq.sqrt() ...)

The fault is stochastic per run (dispatch/shape lottery): 3/3 seeds
crashed on the reference box (i5-3350P), but survivors are possible —
a clean exit does NOT exonerate the hardware, it just drew lucky.
Run several seeds (or raise --epochs) before concluding anything.

Workaround (verified: full survival): MKL_ENABLE_INSTRUCTIONS=SSE4_2.

Usage:
    python3 repro.py [--seed S] [--epochs N] [--sents N]
"""
import argparse
import faulthandler
import random
import sys

import torch
from torch import nn

TAGS = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN",
        "NUM", "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM",
        "VERB", "X"]

VOCAB, NCHARS = 28000, 90


class Tagger(nn.Module):
    def __init__(self, nw, nc):
        super().__init__()
        self.wemb = nn.Embedding(nw, 64, padding_idx=0)
        self.cemb = nn.Embedding(nc, 16, padding_idx=0)
        self.cenc = nn.LSTM(16, 32, batch_first=True, bidirectional=True)
        self.wenc = nn.LSTM(64 + 64, 128, batch_first=True,
                            bidirectional=True)
        self.drop = nn.Dropout(0.33)
        self.out = nn.Linear(256, len(TAGS))

    def forward(self, words, chids):
        # words: (B,T) chids: (B,T,C)
        b, t, c = chids.shape
        ce = self.cemb(chids.view(b * t, c))
        _, (h, _) = self.cenc(ce)  # (2,B*T,32)
        cw = torch.cat([h[0], h[1]], dim=1).view(b, t, 64)
        w = torch.cat([self.wemb(words), cw], dim=2)
        h2, _ = self.wenc(w)
        return self.out(self.drop(h2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--sents", type=int, default=27315)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    faulthandler.enable()
    torch.manual_seed(a.seed)
    random.seed(a.seed)
    torch.set_num_threads(a.threads)

    rng = random.Random(a.seed)
    sents = []
    for _ in range(a.sents):
        n = min(1 + int(rng.expovariate(1 / 18)), 120)
        sents.append((
            [rng.randrange(VOCAB) for _ in range(n)],
            [[rng.randrange(1, NCHARS) for _ in range(rng.randint(1, 10))]
             for _ in range(n)],
            [rng.randrange(len(TAGS)) for _ in range(n)],
        ))
    print(f"sents: {len(sents)}", flush=True)

    m = Tagger(VOCAB + 2, 256)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    lossf = nn.CrossEntropyLoss()
    order = list(range(len(sents)))
    for ep in range(1, a.epochs + 1):
        random.Random(1000 + ep).shuffle(order)
        m.train()
        nb = 0
        for b0 in range(0, len(sents), 32):
            batch = [sents[i] for i in order[b0:b0 + 32]]
            T = max(len(w) for w, _, _ in batch)
            words = torch.zeros(len(batch), T, dtype=torch.long)
            gold = torch.zeros(len(batch), T, dtype=torch.long)
            clen = max(len(r) for _, c, _ in batch for r in c)
            chs = torch.zeros(len(batch), T, clen, dtype=torch.long)
            for i, (w, c, t) in enumerate(batch):
                words[i, :len(w)] = torch.tensor(w)
                gold[i, :len(t)] = torch.tensor(t)
                for j, r in enumerate(c):
                    chs[i, j, :len(r)] = torch.tensor(r)
            logits = m(words, chs)
            loss = lossf(logits.view(-1, len(TAGS)), gold.view(-1))
            opt.zero_grad()
            loss.backward()
            opt.step()
            nb += 1
        print(f"epoch {ep} survived ({nb} batches)", flush=True)
    print("SURVIVED ALL")


if __name__ == "__main__":
    main()
