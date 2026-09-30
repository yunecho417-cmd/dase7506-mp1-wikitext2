"""Student model for MP1 (DASE7506).

A pre-norm decoder-only transformer that keeps the course contract exactly:

  * build_model(config) -> nn.Module with attribute `context == 256`
  * forward(ids)            -> unnormalized logits      [B, T, 2048]
  * predict_log_probs(ids)  -> normalized log probs     [B, T, 2048], strictly causal
  * stateless: every call starts fresh, no cross-window memory

Everything beyond the baseline is controlled by optional config keys, so the
model still builds from the minimal dict used by tests/test_contract.py
(vocab, width, heads, depth, context).

Design notes relative to the provided baseline (model.py):
  1. RMSNorm and SwiGLU are optional so their effects can be isolated.
  2. SwiGLU with ffn_mult = 8/3 is approximately parameter-matched to the
     baseline GELU MLP with ffn_mult = 4.
  3. Position encoding and input/output weight tying are configurable for clean
     validation-only ablations.
"""
import torch
from torch import nn
from torch.nn import functional as F


def _rotate_half(x):
    half = x.shape[-1] // 2
    x1, x2 = x[..., :half], x[..., half:]
    return torch.cat((-x2, x1), dim=-1)


class RMSNorm(nn.Module):
    def __init__(self, width, eps=1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(width))
        self.eps = eps

    def forward(self, x):
        return F.rms_norm(x, x.shape[-1:], self.weight, self.eps)


def make_norm(kind, width):
    return RMSNorm(width) if kind == 'rms' else nn.LayerNorm(width)


class Attention(nn.Module):
    def __init__(self, width, heads, dropout):
        super().__init__()
        self.heads = heads
        self.head_dim = width // heads
        self.qkv = nn.Linear(width, 3 * width, bias=False)
        self.proj = nn.Linear(width, width, bias=False)
        self.drop = nn.Dropout(dropout)

    def forward(self, x, rotary=None):
        b, t, w = x.shape
        q, k, v = self.qkv(x).view(b, t, 3, self.heads, self.head_dim).permute(2, 0, 3, 1, 4)
        if rotary is not None:
            cos, sin = rotary
            q = q * cos + _rotate_half(q) * sin
            k = k * cos + _rotate_half(k) * sin
        attended = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        out = attended.transpose(1, 2).reshape(b, t, w)
        return self.drop(self.proj(out))


class FeedForward(nn.Module):
    def __init__(self, width, hidden, kind, dropout):
        super().__init__()
        self.kind = kind
        self.gate = nn.Linear(width, hidden, bias=False)
        if kind != 'gelu':
            self.up = nn.Linear(width, hidden, bias=False)
        self.down = nn.Linear(hidden, width, bias=False)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        if self.kind == 'gelu':
            h = F.gelu(self.gate(x))
        else:
            h = F.silu(self.gate(x)) * self.up(x)
        return self.drop(self.down(h))


class Block(nn.Module):
    def __init__(self, width, heads, ffn_mult, ffn_kind, norm_kind, dropout):
        super().__init__()
        hidden = max(1, int(width * ffn_mult))
        self.norm1 = make_norm(norm_kind, width)
        self.attn = Attention(width, heads, dropout)
        self.norm2 = make_norm(norm_kind, width)
        self.ff = FeedForward(width, hidden, ffn_kind, dropout)

    def forward(self, x, rotary=None):
        x = x + self.attn(self.norm1(x), rotary)
        return x + self.ff(self.norm2(x))


class Student(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = dict(config)
        self.context = config['context']
        width, heads, depth = config['width'], config['heads'], config['depth']
        self.norm_kind = config.get('norm', 'rms')
        self.ffn_kind = config.get('ffn', 'swiglu')
        ffn_mult = config.get('ffn_mult', 8 / 3)
        self.pos_kind = config.get('pos', 'learned')
        self.tie = bool(config.get('tie', 1))
        dropout = float(config.get('dropout', 0.))
        self.rope_base = float(config.get('rope_base', 10000.))
        init_std = float(config.get('init_std', .02))

        self.token = nn.Embedding(config['vocab'], width)
        if self.pos_kind == 'rope':
            self.pos = None
            inv = 1. / (self.rope_base ** (torch.arange(0, width // heads, 2).float() / (width // heads)))
            self.register_buffer('rope_inv_freq', inv, persistent=False)
        else:
            self.pos = nn.Embedding(self.context, width)
            self.register_buffer('rope_inv_freq', None, persistent=False)
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList(
            [Block(width, heads, ffn_mult, self.ffn_kind, self.norm_kind, dropout)
             for _ in range(depth)])
        self.norm = make_norm(self.norm_kind, width)
        self.head = nn.Linear(width, config['vocab'], bias=False)
        self.apply(lambda m: Student.initialize(m, init_std))
        if self.tie:
            self.head.weight = self.token.weight

    @staticmethod
    def initialize(module, std):
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, std=std)

    def rotary(self, length, device):
        if self.pos_kind != 'rope':
            return None
        t = torch.arange(length, device=device).float()
        freqs = torch.outer(t, self.rope_inv_freq.to(device))
        emb = torch.cat((freqs, freqs), dim=-1)
        # Attention tensors use [batch, heads, time, head_dim]. Keep the
        # singleton dimensions in that order so RoPE broadcasts correctly.
        return emb.cos()[None, None, :, :], emb.sin()[None, None, :, :]

    def features(self, ids):
        x = self.token(ids)
        if self.pos_kind == 'learned':
            x = x + self.pos(torch.arange(ids.shape[1], device=ids.device))
        x = self.drop(x)
        rotary = self.rotary(ids.shape[1], ids.device)
        for block in self.blocks:
            x = block(x, rotary)
        return self.norm(x)

    def forward(self, ids):
        """Training interface: unnormalized next-token logits [batch, time, vocab]."""
        return self.head(self.features(ids))

    def predict_log_probs(self, ids):
        """Evaluation interface: finite, normalized natural-log probabilities.

        Strictly causal within one window and stateless across windows: every call
        recomputes from `ids` alone.
        """
        return F.log_softmax(self(ids).float(), dim=-1)


def build_model(config):
    return Student(config)
