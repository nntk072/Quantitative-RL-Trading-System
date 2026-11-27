from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
import torch
from gymnasium import spaces

from models.encoders.lite_tcn import LiteTCNEncoder
from models.encoders.mtf import MTFEncoder
from models.encoders.mtf_efficiency_components import (
    MTFReasoningOutput,
    batch_mask,
    observation_streams,
)
from models.encoders.mtf_m1_htf_lite_reasoning import M1TCNHTFLiteReasoningEncoder
from models.encoders.mtf_m1_htf_snapshot_reasoning import M1TCNHTFSnapshotReasoningEncoder
from models.encoders.mtf_reasoning import MTFReasoningEncoder
from models.encoders.mtf_shared_tcn_reasoning import SharedTCNMTFReasoningEncoder, _SharedTCNCore

_STREAMS = (
    ("seq", "seq_mask", 60, 5),
    ("seq_m3", "mask_m3", 20, 4),
    ("seq_m5", "mask_m5", 24, 3),
    ("seq_m10", "mask_m10", 12, 6),
    ("seq_m15", "mask_m15", 16, 2),
    ("seq_m30", "mask_m30", 8, 7),
    ("seq_h1", "mask_h1", 12, 4),
    ("seq_h4", "mask_h4", 6, 3),
    ("seq_d1", "mask_d1", 5, 2),
)


def _space() -> spaces.Dict:
    spec: dict[str, spaces.Space[Any]] = {
        "account": spaces.Box(-1.0, 1.0, shape=(6,), dtype=np.float32)
    }
    for seq_key, mask_key, length, width in _STREAMS:
        spec[seq_key] = spaces.Box(-1.0, 1.0, shape=(length, width), dtype=np.float32)
        spec[mask_key] = spaces.Box(0.0, 1.0, shape=(length,), dtype=np.float32)
    return spaces.Dict(spec)


def _observations(batch_size: int = 3) -> dict[str, torch.Tensor]:
    torch.manual_seed(2718)
    result: dict[str, torch.Tensor] = {"account": torch.randn(batch_size, 6)}
    for stream_index, (seq_key, mask_key, length, width) in enumerate(_STREAMS):
        seq = torch.randn(batch_size, length, width)
        mask = torch.ones(batch_size, length)
        # Exercise different left-padding lengths, including a one-row and empty HTF.
        for row in range(batch_size):
            valid_count = max(0, length - ((row + stream_index) % min(length, 4)))
            if stream_index == 7 and row == 1:
                valid_count = 1
            if stream_index == 8 and row == 2:
                valid_count = 0
            mask[row, : length - valid_count] = 0.0
            seq[row, : length - valid_count] = 0.0
        result[seq_key] = seq
        result[mask_key] = mask
    return result


def _encoder_factories() -> tuple[Callable[[], Any], ...]:
    common: dict[str, Any] = {
        "channels": (8, 8),
        "dropout": 0.0,
        "attention_heads": 4,
        "feedforward_dim": 32,
    }
    return (
        lambda: SharedTCNMTFReasoningEncoder(_space(), latent_dim=16, adapter_dim=5, **common),
        lambda: M1TCNHTFLiteReasoningEncoder(_space(), latent_dim=16, adapter_dim=4, **common),
        lambda: M1TCNHTFSnapshotReasoningEncoder(_space(), latent_dim=16, adapter_dim=4, **common),
    )


@pytest.mark.parametrize("factory", _encoder_factories())
def test_efficient_mtf_encoders_have_nine_tokens_finite_gradients_and_provenance(factory) -> None:
    encoder = factory()
    observations = _observations()
    output = encoder(observations)

    assert output.shape == (3, 48)
    assert torch.isfinite(output).all()
    output.square().mean().backward()
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all()
        for parameter in encoder.parameters()
    )
    provenance = encoder.encoder_provenance
    assert provenance["branch_count"] == 9
    assert provenance["token_dim"] == 16
    assert provenance["latent_dim"] == 16
    assert provenance["attention_heads"] == 4
    assert provenance["attention_feedforward_dim"] == 32


@pytest.mark.parametrize("factory", _encoder_factories())
@pytest.mark.parametrize("batch_size", (1, 8, 512))
def test_efficient_mtf_encoder_batch_output_shapes(factory, batch_size: int) -> None:
    encoder = factory().eval()
    with torch.no_grad():
        output = encoder(_observations(batch_size))
    assert output.shape == (batch_size, 48)
    assert torch.isfinite(output).all()


@pytest.mark.parametrize("factory", _encoder_factories())
def test_efficient_mtf_encoders_ignore_all_masked_htf_values(factory) -> None:
    encoder = factory().eval()
    observed = _observations(batch_size=3)
    perturbed = {key: value.clone() for key, value in observed.items()}

    # Keep M1 available but make every higher-timeframe stream unavailable.
    # Changing masked HTF payloads must not change the resulting representation.
    for seq_key, mask_key, _, _ in _STREAMS[1:]:
        observed[mask_key].zero_()
        perturbed[mask_key].zero_()
        perturbed[seq_key] = torch.randn_like(perturbed[seq_key])

    with torch.no_grad():
        expected = encoder(observed)
        actual = encoder(perturbed)

    assert torch.isfinite(expected).all()
    assert torch.isfinite(actual).all()
    torch.testing.assert_close(actual, expected)


def test_shared_tcn_uses_one_temporal_core_for_all_nine_streams() -> None:
    encoder = SharedTCNMTFReasoningEncoder(
        _space(),
        latent_dim=16,
        channels=(8, 8),
        dropout=0.0,
        attention_heads=4,
        feedforward_dim=32,
        adapter_dim=5,
    )

    assert encoder.branch_count == 9
    assert len(encoder.adapters) == 9
    assert encoder.shared_core is True
    assert sum(1 for module in encoder.modules() if module is encoder.temporal_core) == 1
    assert encoder.encoder_provenance["htf_summary_type"] == "shared_causal_tcn"


def test_shared_tcn_keeps_timeframe_specific_input_adapters() -> None:
    spec: dict[str, spaces.Space[Any]] = {
        "account": spaces.Box(-1.0, 1.0, shape=(6,), dtype=np.float32)
    }
    for seq_key, mask_key, length, _ in _STREAMS:
        spec[seq_key] = spaces.Box(-1.0, 1.0, shape=(length, 4), dtype=np.float32)
        spec[mask_key] = spaces.Box(0.0, 1.0, shape=(length,), dtype=np.float32)
    encoder = SharedTCNMTFReasoningEncoder(
        spaces.Dict(spec),
        latent_dim=16,
        channels=(8, 8),
        dropout=0.0,
        attention_heads=4,
        feedforward_dim=32,
        adapter_dim=5,
    ).eval()
    same_normalized_input = torch.ones(2, 5, 4)
    m3_values = encoder.adapters[1](same_normalized_input)
    m5_values = encoder.adapters[2](same_normalized_input)
    timeframe_ids = encoder.timeframe_embedding(encoder.timeframe_ids)

    assert encoder.adapters[1] is not encoder.adapters[2]
    assert not torch.allclose(m3_values, m5_values)
    assert not torch.equal(timeframe_ids[1], timeframe_ids[2])


def test_efficient_encoders_reduce_parameters_and_keep_production_output_width() -> None:
    baseline = MTFReasoningEncoder(
        _space(), latent_dim=16, channels=(8, 8), dropout=0.0, attention_heads=4
    )
    baseline_parameters = sum(parameter.numel() for parameter in baseline.parameters())
    for factory in _encoder_factories():
        encoder = factory()
        assert sum(parameter.numel() for parameter in encoder.parameters()) < baseline_parameters

    for encoder_class in (
        SharedTCNMTFReasoningEncoder,
        M1TCNHTFLiteReasoningEncoder,
        M1TCNHTFSnapshotReasoningEncoder,
    ):
        assert encoder_class(_space()).features_dim == 160


def test_shared_tcn_masked_padding_values_do_not_change_output() -> None:
    encoder = _encoder_factories()[0]().eval()
    original = _observations()
    changed = {key: value.clone() for key, value in original.items()}
    for seq_key, mask_key, _, _ in _STREAMS:
        invalid = original[mask_key] == 0
        changed[seq_key][invalid] = torch.randn_like(changed[seq_key][invalid]) * 1e4

    with torch.no_grad():
        torch.testing.assert_close(encoder(original), encoder(changed), rtol=0.0, atol=0.0)


@pytest.mark.parametrize("factory", _encoder_factories())
def test_all_encoders_ignore_nonfinite_masked_padding(factory) -> None:
    encoder = factory().eval()
    original = _observations()
    poisoned = {key: value.clone() for key, value in original.items()}
    for seq_key, mask_key, _, _ in _STREAMS:
        poisoned[seq_key][original[mask_key] == 0] = torch.nan

    with torch.no_grad():
        expected = encoder(original)
        actual = encoder(poisoned)
    assert torch.isfinite(actual).all()
    torch.testing.assert_close(expected, actual, rtol=0.0, atol=0.0)


def test_lite_htf_encoder_responds_to_earlier_valid_history() -> None:
    encoder = _encoder_factories()[1]().eval()
    original = _observations()
    changed = {key: value.clone() for key, value in original.items()}
    # M5 is left-padded; alter a valid row while holding its latest row fixed.
    changed["seq_m5"][:, -2] += 3.0

    with torch.no_grad():
        reference = encoder(original)
        history_changed = encoder(changed)
    assert not torch.allclose(reference, history_changed)
    assert (
        encoder.encoder_provenance["htf_summary_type"] == "latest_masked_mean_and_change_shared_mlp"
    )


def test_lite_encoder_backpropagates_through_each_reasoning_stage() -> None:
    encoder = _encoder_factories()[1]()
    encoder(_observations()).square().mean().backward()

    for name, module in (
        ("M1 TCN", encoder.m1_tcn),
        ("HTF adapters", encoder.htf_adapters),
        ("HTF summary", encoder.htf_summary),
        ("timeframe attention", encoder.cross_timeframe),
        ("timeframe identity", encoder.timeframe_embedding),
    ):
        gradients = [
            parameter.grad
            for parameter in module.parameters()
            if parameter.requires_grad and parameter.grad is not None
        ]
        assert gradients, f"{name} received no gradients"
        assert all(torch.isfinite(gradient).all() for gradient in gradients), name
        assert sum(float(gradient.abs().sum()) for gradient in gradients) > 0.0, name


def test_snapshot_htf_encoder_ignores_history_but_uses_latest_valid_state() -> None:
    encoder = _encoder_factories()[2]().eval()
    original = _observations()
    history_changed = {key: value.clone() for key, value in original.items()}
    latest_changed = {key: value.clone() for key, value in original.items()}
    for seq_key, mask_key, _, _ in _STREAMS[1:]:
        non_latest_valid = (original[mask_key] > 0).clone()
        non_latest_valid[:, -1] = False
        history_changed[seq_key][non_latest_valid] += 100.0
        latest_changed[seq_key][:, -1] += 2.0

    with torch.no_grad():
        reference = encoder(original)
        history_output = encoder(history_changed)
        latest_output = encoder(latest_changed)
    torch.testing.assert_close(reference, history_output, rtol=0.0, atol=0.0)
    assert not torch.allclose(reference, latest_output)
    assert encoder.encoder_provenance["htf_summary_type"] == "latest_valid_snapshot_shared_mlp"


def test_efficient_mtf_space_and_mask_contracts_fail_closed() -> None:
    with pytest.raises(TypeError, match="Dict observation space"):
        observation_streams(spaces.Box(-1.0, 1.0, shape=(6,)))

    missing_stream = dict(_space().spaces)
    del missing_stream["seq_m5"]
    with pytest.raises(ValueError, match="require seq_m5 and mask_m5"):
        observation_streams(spaces.Dict(missing_stream))

    mismatched_mask = dict(_space().spaces)
    mismatched_mask["mask_m5"] = spaces.Box(0.0, 1.0, shape=(99,))
    with pytest.raises(ValueError, match="mask_m5 must match"):
        observation_streams(spaces.Dict(mismatched_mask))

    no_account = dict(_space().spaces)
    del no_account["account"]
    with pytest.raises(ValueError, match="account observation"):
        observation_streams(spaces.Dict(no_account))

    with pytest.raises(ValueError, match="mask length"):
        batch_mask(torch.ones(1, 4), batch_size=1, timesteps=3)
    with pytest.raises(ValueError, match="mask batch size"):
        batch_mask(torch.ones(2, 3), batch_size=1, timesteps=3)
    assert batch_mask(torch.tensor([1, 0, 1]), batch_size=2, timesteps=3).shape == (2, 3)


def test_mtf_reasoning_output_rejects_invalid_dimensions_and_masks() -> None:
    with pytest.raises(ValueError, match="divisible by attention_heads"):
        MTFReasoningOutput(
            _space(),
            latent_dim=10,
            account_dim=None,
            attention_heads=4,
            feedforward_dim=32,
            dropout=0.0,
        )

    module = MTFReasoningOutput(
        _space(),
        latent_dim=8,
        account_dim=None,
        attention_heads=2,
        feedforward_dim=16,
        dropout=0.0,
    )
    with pytest.raises(ValueError, match="MTF tokens must have shape"):
        module.finish(torch.zeros(2, 8, 8), torch.ones(2, 8, dtype=torch.bool), torch.zeros(2, 6))
    with pytest.raises(ValueError, match="validity mask must have shape"):
        module.finish(torch.zeros(2, 9, 8), torch.ones(2, 8, dtype=torch.bool), torch.zeros(2, 6))


@pytest.mark.parametrize(
    "kwargs",
    [{"dilations": ()}, {"dilations": (0,)}, {"channels": 0}, {"kernel_size": 0}],
)
def test_lite_tcn_rejects_empty_or_nonpositive_convolution_parameters(
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="LiteTCN"):
        LiteTCNEncoder(_space(), **kwargs)


def test_mtf_reasoning_encoder_rejects_incompatible_attention_width() -> None:
    with pytest.raises(ValueError, match="divisible by attention_heads"):
        MTFReasoningEncoder(
            _space(),
            latent_dim=10,
            channels=(8, 8),
            dropout=0.0,
            attention_heads=4,
        )


@pytest.mark.parametrize(
    ("spec", "exception", "message"),
    [
        (
            spaces.Box(-1.0, 1.0, shape=(6,)),
            TypeError,
            "Dict observation space",
        ),
        (
            spaces.Dict(
                {
                    "account": spaces.Box(-1.0, 1.0, shape=(6,)),
                    "seq_m5": spaces.Box(-1.0, 1.0, shape=(4, 2)),
                    "mask_m5": spaces.Box(0.0, 1.0, shape=(4,)),
                }
            ),
            ValueError,
            "M1 'seq' observation stream",
        ),
        (
            spaces.Dict(
                {
                    "account": spaces.Box(-1.0, 1.0, shape=(6,)),
                    "seq": spaces.Box(-1.0, 1.0, shape=(4, 2)),
                }
            ),
            ValueError,
            "missing mask observation",
        ),
        (
            spaces.Dict(
                {
                    "account": spaces.Box(-1.0, 1.0, shape=(6,)),
                    "seq": spaces.Box(-1.0, 1.0, shape=(2,)),
                    "seq_mask": spaces.Box(0.0, 1.0, shape=(2,)),
                }
            ),
            TypeError,
            "seq must be a Box",
        ),
    ],
)
def test_mtf_encoder_rejects_invalid_observation_spaces(spec, exception, message) -> None:
    with pytest.raises(exception, match=message):
        MTFEncoder(spec, latent_dim=8, channels=(4,), dropout=0.0)


def test_efficient_mtf_stream_contract_rejects_non_matrix_sequence() -> None:
    observation_space = spaces.Dict(
        {
            "account": spaces.Box(-1.0, 1.0, shape=(6,)),
            "seq": spaces.Box(-1.0, 1.0, shape=(60,)),
            "seq_mask": spaces.Box(0.0, 1.0, shape=(60,)),
        }
    )

    with pytest.raises(TypeError, match=r"seq must have a \(window, features\) shape"):
        observation_streams(observation_space)


def test_shared_tcn_core_requires_at_least_one_channel() -> None:
    with pytest.raises(ValueError, match="channels must contain at least one width"):
        _SharedTCNCore(4, 8, (), 3, 0.0)


@pytest.mark.parametrize(
    "encoder_type",
    [
        SharedTCNMTFReasoningEncoder,
        M1TCNHTFLiteReasoningEncoder,
        M1TCNHTFSnapshotReasoningEncoder,
    ],
)
def test_efficient_mtf_encoders_reject_nonpositive_adapter_width(encoder_type) -> None:
    with pytest.raises(ValueError, match="adapter_dim must be positive"):
        encoder_type(
            _space(),
            latent_dim=16,
            channels=(8, 8),
            dropout=0.0,
            attention_heads=4,
            feedforward_dim=32,
            adapter_dim=0,
        )
