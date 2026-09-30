"""Unit tests for the configurable training controls used by ablations."""

import math
import unittest

import torch

from train_student import (
    PermutationBatchLoader,
    RandomBatchLoader,
    get_baseline_lr,
    get_lr,
)


class TrainerControlTests(unittest.TestCase):
    def test_baseline_schedule_matches_supplied_formula(self):
        for step in (0, 49, 99, 100, 1199):
            expected = .001 * min(1., (step + 1) / 100) * (
                .1 + .9 * .5 * (1 + math.cos(math.pi * step / 1200)))
            self.assertAlmostEqual(
                get_baseline_lr(step, 1200, .001, 100, .1), expected, places=15)

    def test_cosine_schedule_ends_near_minimum(self):
        values = [get_lr(step, 1200, .001, 36, .1) for step in range(1200)]
        self.assertGreater(values[36], values[-1])
        self.assertAlmostEqual(values[-1], .0001, places=8)

    def test_random_loader_is_seed_reproducible(self):
        tokens = torch.arange(2000)
        a = RandomBatchLoader(tokens, 16, 17).next(8)
        b = RandomBatchLoader(tokens, 16, 17).next(8)
        torch.testing.assert_close(a, b)

    def test_permutation_loader_has_unique_starts_before_wrap(self):
        tokens = torch.arange(2000)
        batch = PermutationBatchLoader(tokens, 16, 17).next(64)
        self.assertEqual(len(set(batch[:, 0].tolist())), 64)


if __name__ == '__main__':
    unittest.main()
