"""Tests for sequence encoder implementations (TCN, Transformer, GRU)."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, cast

import numpy as np
import pytest
import torch
from gymnasium import spaces
from torch import nn

from models.encoders import (
    GRUEncoder,
    LiteTCNEncoder,
    MTFEmptyStreamMaskedV1Encoder,
    MTFEncoder,
    MTFReasoningEncoder,
    TCNEncoder,
    TransformerEncoder,
)
from models.encoders.mtf_efficiency_components import observation_streams
from models.encoders.sequence_encoder_components import _resolve_account_dim, _valid_lengths
from models.factory import encoder_for
from models.runtime import precision as encoder_precision


@pytest.mark.parametrize(
    "encoder_cls", [TCNEncoder, TransformerEncoder, GRUEncoder, LiteTCNEncoder]
)
def test_single_stream_encoders_accept_widened_validity_channel_inputs(
    encoder_cls: type[Any],
) -> None:
    feature_count = 12  # six values followed by six finite-value channels
    observation_space = spaces.Dict(
        {
            "seq": spaces.Box(low=-1.0, high=1.0, shape=(8, feature_count), dtype=np.float32),
            "seq_mask": spaces.Box(low=0.0, high=1.0, shape=(8,), dtype=np.float32),
            "account": spaces.Box(low=-1.0, high=1.0, shape=(10,), dtype=np.float32),
        }
    )
    encoder = encoder_cls(
        observation_space=observation_space,
        seq_len=8,
        n_features=feature_count,
        latent_dim=16,
    ).eval()
    observations = {
        "seq": torch.zeros(2, 8, feature_count),
        "seq_mask": torch.ones(2, 8),
        "account": torch.zeros(2, 10),
    }

    output = encoder(observations)

    assert output.shape == (2, 48)
    assert torch.isfinite(output).all()


def test_legacy_encoder_core_path_reexports_registered_encoder_classes() -> None:
    from models.encoders import core as legacy_encoder_exports

    assert legacy_encoder_exports.GRUEncoder is GRUEncoder
    assert legacy_encoder_exports.LiteTCNEncoder is LiteTCNEncoder
    assert legacy_encoder_exports.MTFEncoder is MTFEncoder
    assert legacy_encoder_exports.TCNEncoder is TCNEncoder
    assert legacy_encoder_exports.TransformerEncoder is TransformerEncoder


class TestTCNEncoder:
    """Tests for TCNEncoder class."""

    def test_tcn_observation_space(self) -> None:
        """Test TCNEncoder with proper observation space."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = TCNEncoder(
            observation_space=observation_space,
            seq_len=60,
            n_features=64,
            latent_dim=128,
        )

        assert encoder.features_dim == 128 + 32  # latent_dim + account embedding
        assert encoder.dilations == (1, 2, 4, 8)
        assert encoder.receptive_field == 61

    def test_tcn_forward(self) -> None:
        """Test TCNEncoder forward pass."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = TCNEncoder(
            observation_space=observation_space,
            seq_len=60,
            n_features=64,
            latent_dim=128,
        )

        # Create dummy observations
        batch_size = 8
        obs = {
            "seq": torch.randn(batch_size, 60, 64),
            "account": torch.randn(batch_size, 6),
        }

        output = encoder(obs)

        assert output.shape == (batch_size, 128 + 32)


class TestLiteTCNEncoder:
    @staticmethod
    def _space(n_features: int = 194) -> spaces.Dict:
        return spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, n_features), dtype=np.float32),
                "seq_mask": spaces.Box(low=0.0, high=1.0, shape=(60,), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

    def test_shape_and_receptive_field_match_observation_contract(self) -> None:
        encoder = LiteTCNEncoder(self._space(), seq_len=60, n_features=194)
        output = encoder({"seq": torch.randn(3, 60, 194), "account": torch.randn(3, 6)})
        assert output.shape == (3, 160)
        assert encoder.receptive_field == 61
        assert encoder.receptive_field >= encoder.seq_len

    def test_left_padding_values_do_not_change_output(self) -> None:
        encoder = LiteTCNEncoder(self._space(), seq_len=60, n_features=194).eval()
        seq = torch.randn(2, 60, 194)
        mask = torch.ones(2, 60)
        mask[0, :20] = 0.0
        changed = seq.clone()
        changed[0, :20] = torch.randn_like(changed[0, :20]) * 1000.0
        account = torch.randn(2, 6)

        original_output = encoder({"seq": seq, "seq_mask": mask, "account": account})
        changed_output = encoder({"seq": changed, "seq_mask": mask, "account": account})

        torch.testing.assert_close(original_output, changed_output, rtol=0.0, atol=0.0)

    def test_causal_hidden_states_do_not_depend_on_future_inputs(self) -> None:
        encoder = LiteTCNEncoder(self._space(), seq_len=60, n_features=194).eval()
        seq = torch.randn(2, 60, 194)
        changed = seq.clone()
        changed[:, 31:, :] = torch.randn_like(changed[:, 31:, :]) * 100.0

        original_hidden = encoder._encode_hidden(seq)
        changed_hidden = encoder._encode_hidden(changed)

        torch.testing.assert_close(
            original_hidden[:, :31], changed_hidden[:, :31], rtol=0.0, atol=0.0
        )

    def test_parameter_count_is_substantially_below_tcn(self) -> None:
        space = self._space()
        tcn = TCNEncoder(space, seq_len=60, n_features=194)
        lite = LiteTCNEncoder(space, seq_len=60, n_features=194)
        tcn_count = sum(parameter.numel() for parameter in tcn.parameters())
        lite_count = sum(parameter.numel() for parameter in lite.parameters())
        assert lite_count <= 0.30 * tcn_count

    def test_fp32_forward_and_gradients_are_finite(self) -> None:
        encoder = LiteTCNEncoder(self._space(), seq_len=60, n_features=194)
        output = encoder({"seq": torch.randn(4, 60, 194), "account": torch.randn(4, 6)})
        output.square().mean().backward()

        assert torch.isfinite(output).all()
        assert all(
            parameter.grad is None or torch.isfinite(parameter.grad).all()
            for parameter in encoder.parameters()
        )

    @pytest.mark.gpu
    @pytest.mark.skipif(
        not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(),
        reason="requires a CUDA or ROCm device with BF16 support",
    )
    def test_cuda_bf16_forward_and_gradients_are_finite_when_available(self) -> None:
        encoder = LiteTCNEncoder(self._space(), seq_len=60, n_features=194).cuda()
        obs = {
            "seq": torch.randn(2, 60, 194, device="cuda"),
            "account": torch.randn(2, 6, device="cuda"),
        }
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            output = encoder(obs)
            loss = output.float().square().mean()
        loss.backward()

        assert torch.isfinite(output).all()
        assert torch.isfinite(loss)
        assert all(
            parameter.grad is None or torch.isfinite(parameter.grad).all()
            for parameter in encoder.parameters()
        )

    def test_account_mlp_uses_runtime_observation_dimension(self) -> None:
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 8), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(10,), dtype=np.float32),
            }
        )
        encoder = TCNEncoder(observation_space, seq_len=60, n_features=8, latent_dim=16)
        assert encoder.account_mlp.net[0].in_features == 10
        output = encoder({"seq": torch.randn(2, 60, 8), "account": torch.randn(2, 10)})
        assert output.shape == (2, 16 + 32)


class TestTransformerEncoder:
    """Tests for TransformerEncoder class."""

    def test_transformer_observation_space(self) -> None:
        """Test TransformerEncoder with proper observation space."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = TransformerEncoder(
            observation_space=observation_space,
            seq_len=60,
            n_features=64,
            latent_dim=128,
        )

        assert encoder.features_dim == 128 + 32

    def test_transformer_forward(self) -> None:
        """Test TransformerEncoder forward pass."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = TransformerEncoder(
            observation_space=observation_space,
            seq_len=60,
            n_features=64,
            latent_dim=128,
        )

        obs = {
            "seq": torch.randn(8, 60, 64),
            "account": torch.randn(8, 6),
        }

        output = encoder(obs)

        assert output.shape == (8, 128 + 32)


class TestGRUEncoder:
    """Tests for GRUEncoder class."""

    def test_gru_observation_space(self) -> None:
        """Test GRUEncoder with proper observation space."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(128, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = GRUEncoder(
            observation_space=observation_space,
            seq_len=128,
            n_features=64,
            latent_dim=128,
        )

        assert encoder.features_dim == 128 + 32

    def test_gru_forward(self) -> None:
        """Test GRUEncoder forward pass."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(128, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = GRUEncoder(
            observation_space=observation_space,
            seq_len=128,
            n_features=64,
            latent_dim=128,
        )

        obs = {
            "seq": torch.randn(8, 128, 64),
            "account": torch.randn(8, 6),
        }

        output = encoder(obs)

        assert output.shape == (8, 128 + 32)

    def test_gru_parameters(self) -> None:
        """Test GRUEncoder has trainable parameters."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(128, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = GRUEncoder(observation_space=observation_space)

        total_params = sum(p.numel() for p in encoder.parameters())
        assert total_params > 0, "GRUEncoder should have trainable parameters"

    def test_gru_default_parameters(self) -> None:
        """Test GRUEncoder with default parameters."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(128, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        encoder = GRUEncoder(observation_space=observation_space)

        # Check default values
        assert encoder.seq_len == 128
        assert encoder.n_features == 64
        assert encoder.latent_dim == 128
        assert encoder.hidden_size == 256
        assert encoder.num_layers == 2


class TestEncoderComparison:
    """Tests comparing different encoder implementations."""

    def test_encoders_same_output_shape(self) -> None:
        """Test that all encoders produce the same output shape."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        tcn = TCNEncoder(
            observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
        )
        transformer = TransformerEncoder(
            observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
        )
        gru = GRUEncoder(
            observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
        )

        obs = {
            "seq": torch.randn(8, 60, 64),
            "account": torch.randn(8, 6),
        }

        tcn_out = tcn(obs)
        transformer_out = transformer(obs)
        gru_out = gru(obs)

        assert tcn_out.shape == (8, 128 + 32)
        assert transformer_out.shape == (8, 128 + 32)
        assert gru_out.shape == (8, 128 + 32)

    def test_encoders_accept_dict_input(self) -> None:
        """Test that all encoders accept dict input."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )

        for EncoderClass in [TCNEncoder, TransformerEncoder, GRUEncoder]:
            encoder = EncoderClass(
                observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
            )

            obs = {
                "seq": torch.randn(4, 60, 64),
                "account": torch.randn(4, 6),
            }

            # Should not raise an error
            output = encoder(obs)
            assert output.shape[0] == 4

    def test_encoder_output_changes_with_seq(self) -> None:
        """Encoder output must depend on the sequence input."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )
        encoder = TCNEncoder(
            observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
        )
        obs1 = {
            "seq": torch.randn(2, 60, 64),
            "account": torch.randn(2, 6),
        }
        obs2 = {
            "seq": torch.randn(2, 60, 64),
            "account": obs1["account"],
        }
        out1 = encoder(obs1)
        out2 = encoder(obs2)
        assert not torch.allclose(out1, out2)

    def test_encoder_output_changes_with_account(self) -> None:
        """Encoder output must depend on the account input."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )
        encoder = TransformerEncoder(
            observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
        )
        obs1 = {
            "seq": torch.randn(2, 60, 64),
            "account": torch.randn(2, 6),
        }
        obs2 = {
            "seq": obs1["seq"],
            "account": torch.randn(2, 6),
        }
        out1 = encoder(obs1)
        out2 = encoder(obs2)
        assert not torch.allclose(out1, out2)

    def test_encoder_deterministic_tcn(self) -> None:
        """Same input must produce identical output."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )
        encoder = TCNEncoder(
            observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
        )
        encoder.eval()
        seq = torch.randn(2, 60, 64)
        account = torch.randn(2, 6)
        obs = {"seq": seq, "account": account}
        with torch.no_grad():
            out1 = encoder(obs)
            out2 = encoder(obs)
        assert torch.allclose(out1, out2)

    def test_encoder_deterministic_transformer(self) -> None:
        """Same input must produce identical output."""
        observation_space = spaces.Dict(
            {
                "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 64), dtype=np.float32),
                "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
            }
        )
        encoder = TransformerEncoder(
            observation_space=observation_space, seq_len=60, n_features=64, latent_dim=128
        )
        encoder.eval()
        seq = torch.randn(2, 60, 64)
        account = torch.randn(2, 6)
        obs = {"seq": seq, "account": account}
        with torch.no_grad():
            out1 = encoder(obs)
            out2 = encoder(obs)
        assert torch.allclose(out1, out2)


def _small_encoder(kind: str, timesteps: int = 12, n_features: int = 4) -> Any:
    observation_space = spaces.Dict(
        {
            "seq": spaces.Box(
                low=-np.inf, high=np.inf, shape=(timesteps, n_features), dtype=np.float32
            ),
            "account": spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32),
        }
    )
    if kind == "tcn":
        model: Any = TCNEncoder(
            observation_space,
            seq_len=timesteps,
            n_features=n_features,
            latent_dim=8,
            channels=(8, 8),
            kernel_size=3,
            dropout=0.0,
        )
    elif kind == "gru":
        model = GRUEncoder(
            observation_space,
            seq_len=timesteps,
            n_features=n_features,
            latent_dim=8,
            hidden_size=8,
            num_layers=1,
            dropout=0.0,
        )
    else:
        model = TransformerEncoder(
            observation_space,
            seq_len=timesteps,
            n_features=n_features,
            latent_dim=8,
            d_model=8,
            nhead=2,
            num_layers=1,
            dim_feedforward=16,
            dropout=0.0,
        )
    model.eval()
    return model


def test_valid_suffix_ignores_left_pad_values() -> None:
    """Same valid suffix, pad 0 versus 9/-3/100. First real bar is position 0."""
    torch.manual_seed(0)
    timesteps, length, n_features = 12, 5, 4
    suffix = torch.randn(2, length, n_features)
    account = torch.randn(2, 6)
    zeros = torch.zeros(2, timesteps, n_features)
    zeros[:, -length:] = suffix
    poison = zeros.clone()
    poison[:, :-length] = torch.tensor([9.0, -3.0, 100.0, 0.0])
    mask = torch.zeros(2, timesteps)
    mask[:, -length:] = 1.0
    for kind in ("tcn", "gru", "transformer"):
        model = _small_encoder(kind, timesteps, n_features)
        with torch.no_grad():
            padded = model({"seq": zeros, "seq_mask": mask, "account": account})
            poisoned = model({"seq": poison, "seq_mask": mask, "account": account})
            short = model({"seq": suffix, "account": account})
        assert torch.allclose(padded, poisoned, atol=1e-5), kind
        assert torch.allclose(padded, short, atol=1e-5), kind


def test_mixed_valid_lengths_match_rowwise_suffix() -> None:
    torch.manual_seed(1)
    timesteps, n_features = 10, 4
    seq = torch.randn(2, timesteps, n_features)
    account = torch.randn(2, 6)
    lengths = (7, 4)
    mask = torch.zeros(2, timesteps)
    for row, length in enumerate(lengths):
        mask[row, -length:] = 1.0
    for kind in ("tcn", "gru", "transformer"):
        model = _small_encoder(kind, timesteps, n_features)
        with torch.no_grad():
            mixed = model({"seq": seq, "seq_mask": mask, "account": account})
            for row, length in enumerate(lengths):
                alone = model(
                    {
                        "seq": seq[row : row + 1, -length:],
                        "account": account[row : row + 1],
                    }
                )
                assert torch.allclose(mixed[row : row + 1], alone, atol=1e-5), kind


def _mtf_space() -> spaces.Dict:
    return spaces.Dict(
        {
            "seq": spaces.Box(low=-1.0, high=1.0, shape=(8, 3), dtype=np.float32),
            "seq_mask": spaces.Box(low=0.0, high=1.0, shape=(8,), dtype=np.float32),
            "seq_m5": spaces.Box(low=-1.0, high=1.0, shape=(6, 2), dtype=np.float32),
            "mask_m5": spaces.Box(low=0.0, high=1.0, shape=(6,), dtype=np.float32),
            "seq_m15": spaces.Box(low=-1.0, high=1.0, shape=(4, 1), dtype=np.float32),
            "mask_m15": spaces.Box(low=0.0, high=1.0, shape=(4,), dtype=np.float32),
            "seq_h1": spaces.Box(low=-1.0, high=1.0, shape=(4, 1), dtype=np.float32),
            "mask_h1": spaces.Box(low=0.0, high=1.0, shape=(4,), dtype=np.float32),
            "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
        }
    )


def test_mtf_encoder_returns_160() -> None:
    encoder = MTFEncoder(_mtf_space(), latent_dim=128, channels=(8, 8), dropout=0.0)
    encoder.eval()
    batch = 2
    obs = {
        "seq": torch.randn(batch, 8, 3),
        "seq_mask": torch.ones(batch, 8),
        "seq_m5": torch.randn(batch, 6, 2),
        "mask_m5": torch.ones(batch, 6),
        "seq_m15": torch.randn(batch, 4, 1),
        "mask_m15": torch.ones(batch, 4),
        "seq_h1": torch.randn(batch, 4, 1),
        "mask_h1": torch.ones(batch, 4),
        "account": torch.randn(batch, 6),
    }
    assert encoder(obs).shape == (batch, 160)


def test_mtf_empty_stream_masked_v1_ignores_unavailable_stream_payloads() -> None:
    torch.manual_seed(31)
    encoder = MTFEmptyStreamMaskedV1Encoder(
        _mtf_space(), latent_dim=16, channels=(8, 8), dropout=0.0
    )
    encoder.eval()
    observations = {
        "seq": torch.randn(2, 8, 3),
        "seq_mask": torch.ones(2, 8),
        "seq_m5": torch.randn(2, 6, 2),
        "mask_m5": torch.ones(2, 6),
        "seq_m15": torch.randn(2, 4, 1),
        "mask_m15": torch.ones(2, 4),
        "seq_h1": torch.randn(2, 4, 1),
        "mask_h1": torch.zeros(2, 4),
        "account": torch.randn(2, 6),
    }
    perturbed = {key: value.clone() for key, value in observations.items()}
    perturbed["seq_h1"] = torch.randn_like(perturbed["seq_h1"]) * 100.0

    with torch.no_grad():
        actual = encoder(observations)
        changed = encoder(perturbed)

    torch.testing.assert_close(actual, changed, rtol=0.0, atol=0.0)


def test_mtf_empty_stream_masked_v1_preserves_legacy_parameter_schema() -> None:
    legacy = MTFEncoder(_mtf_space(), latent_dim=16, channels=(8, 8), dropout=0.0)
    masked = MTFEmptyStreamMaskedV1Encoder(
        _mtf_space(), latent_dim=16, channels=(8, 8), dropout=0.0
    )

    assert encoder_for("mtf") is MTFEncoder
    assert encoder_for("mtf_empty_stream_masked_v1") is MTFEmptyStreamMaskedV1Encoder
    assert {key: tuple(value.shape) for key, value in legacy.state_dict().items()} == {
        key: tuple(value.shape) for key, value in masked.state_dict().items()
    }
    masked.load_state_dict(legacy.state_dict())


def test_mtf_encoder_accepts_additional_timeframe_windows() -> None:
    observation_space = spaces.Dict(
        {
            "seq": spaces.Box(low=-1.0, high=1.0, shape=(60, 3), dtype=np.float32),
            "seq_mask": spaces.Box(low=0.0, high=1.0, shape=(60,), dtype=np.float32),
            "seq_m3": spaces.Box(low=-1.0, high=1.0, shape=(20, 2), dtype=np.float32),
            "mask_m3": spaces.Box(low=0.0, high=1.0, shape=(20,), dtype=np.float32),
            "seq_m10": spaces.Box(low=-1.0, high=1.0, shape=(12, 2), dtype=np.float32),
            "mask_m10": spaces.Box(low=0.0, high=1.0, shape=(12,), dtype=np.float32),
            "seq_h4": spaces.Box(low=-1.0, high=1.0, shape=(6, 2), dtype=np.float32),
            "mask_h4": spaces.Box(low=0.0, high=1.0, shape=(6,), dtype=np.float32),
            "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
        }
    )
    encoder = MTFEncoder(observation_space, latent_dim=16, channels=(8, 8), dropout=0.0)
    observations = {
        "seq": torch.randn(2, 60, 3),
        "seq_mask": torch.ones(2, 60),
        "seq_m3": torch.randn(2, 20, 2),
        "mask_m3": torch.ones(2, 20),
        "seq_m10": torch.randn(2, 12, 2),
        "mask_m10": torch.ones(2, 12),
        "seq_h4": torch.randn(2, 6, 2),
        "mask_h4": torch.ones(2, 6),
        "account": torch.randn(2, 6),
    }

    assert len(encoder.branches) == 4
    assert encoder(observations).shape == (2, 48)


def test_mtf_pad_prefix_does_not_change_the_branch() -> None:
    torch.manual_seed(0)
    encoder = MTFEncoder(_mtf_space(), latent_dim=128, channels=(8, 8), dropout=0.0)
    encoder.eval()
    obs = {
        "seq": torch.randn(2, 8, 3),
        "seq_mask": torch.tensor(
            [[0, 0, 0, 1, 1, 1, 1, 1], [0, 0, 1, 1, 1, 1, 1, 1]],
            dtype=torch.float32,
        ),
        "seq_m5": torch.randn(2, 6, 2),
        "mask_m5": torch.tensor([[0, 0, 1, 1, 1, 1]]).expand(2, -1).contiguous(),
        "seq_m15": torch.randn(2, 4, 1),
        "mask_m15": torch.ones(2, 4),
        "seq_h1": torch.zeros(2, 4, 1),
        "mask_h1": torch.zeros(2, 4),
        "account": torch.randn(2, 6),
    }
    with torch.no_grad():
        first = encoder(obs)
        shifted = {key: value.clone() for key, value in obs.items()}
        shifted["seq_m5"][:, :2] = 50.0
        shifted["seq"][:, :2] = -50.0
        shifted["seq_h1"][:, :3] = 7.0
        second = encoder(shifted)
    assert torch.allclose(first, second, atol=1e-5)


def test_mtf_reasoning_encoder_interacts_across_valid_timeframe_tokens() -> None:
    torch.manual_seed(7)
    encoder = MTFReasoningEncoder(
        _mtf_space(), latent_dim=16, channels=(8, 8), dropout=0.0, attention_heads=4
    )
    encoder.eval()
    obs = {
        "seq": torch.randn(2, 8, 3),
        "seq_mask": torch.tensor([[0, 0, 1, 1, 1, 1, 1, 1]]).expand(2, -1).clone(),
        "seq_m5": torch.randn(2, 6, 2),
        "mask_m5": torch.tensor([[0, 0, 1, 1, 1, 1]]).expand(2, -1).clone(),
        "seq_m15": torch.randn(2, 4, 1),
        "mask_m15": torch.ones(2, 4),
        "seq_h1": torch.randn(2, 4, 1),
        "mask_h1": torch.ones(2, 4),
        "account": torch.randn(2, 6),
    }
    with torch.no_grad():
        reference = encoder(obs)
        changed = {key: value.clone() for key, value in obs.items()}
        changed["seq_m5"][:, -1] += 2.0
        alternative = encoder(changed)
        padded = {key: value.clone() for key, value in obs.items()}
        padded["seq"][:, :2] = 1e6
        padded["seq_m5"][:, :2] = -1e6
        ignored = encoder(padded)
    assert reference.shape == (2, 48)
    assert not torch.allclose(reference, alternative)
    assert torch.allclose(reference, ignored, atol=1e-5)

    encoder.train()
    encoder(obs).sum().backward()
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all()
        for parameter in encoder.parameters()
    )


def test_mtf_reasoning_encoder_ignores_payloads_for_empty_htf_windows() -> None:
    torch.manual_seed(23)
    encoder = MTFReasoningEncoder(
        _mtf_space(), latent_dim=16, channels=(8, 8), dropout=0.0, attention_heads=4
    ).eval()
    observations = {
        "seq": torch.randn(2, 8, 3),
        "seq_mask": torch.ones(2, 8),
        "seq_m5": torch.zeros(2, 6, 2),
        "mask_m5": torch.zeros(2, 6),
        "seq_m15": torch.zeros(2, 4, 1),
        "mask_m15": torch.zeros(2, 4),
        "seq_h1": torch.zeros(2, 4, 1),
        "mask_h1": torch.zeros(2, 4),
        "account": torch.randn(2, 6),
    }
    changed = {key: value.clone() for key, value in observations.items()}
    changed["seq_m5"] = torch.randn_like(changed["seq_m5"]) * 100.0
    changed["seq_m15"] = torch.randn_like(changed["seq_m15"]) * 100.0
    changed["seq_h1"] = torch.randn_like(changed["seq_h1"]) * 100.0

    with torch.no_grad():
        expected = encoder(observations)
        actual = encoder(changed)

    torch.testing.assert_close(actual, expected, rtol=0.0, atol=0.0)


def test_mtf_reasoning_encoder_uses_earlier_history_with_latest_candle_fixed() -> None:
    """The configured encoder responds to prior path information, not only final rows."""
    torch.manual_seed(19)
    encoder = MTFReasoningEncoder(
        _mtf_space(), latent_dim=16, channels=(8, 8), dropout=0.0, attention_heads=4
    ).eval()
    obs = {
        "seq": torch.randn(2, 8, 3),
        "seq_mask": torch.ones(2, 8),
        "seq_m5": torch.randn(2, 6, 2),
        "mask_m5": torch.ones(2, 6),
        "seq_m15": torch.randn(2, 4, 1),
        "mask_m15": torch.ones(2, 4),
        "seq_h1": torch.randn(2, 4, 1),
        "mask_h1": torch.ones(2, 4),
        "account": torch.randn(2, 6),
    }
    changed = {key: value.clone() for key, value in obs.items()}
    changed["seq_m5"][:, -2] += 3.0
    latest_before = torch.cat(
        [
            obs[key][:, -1].reshape(len(obs[key]), -1)
            for key in ("seq", "seq_m5", "seq_m15", "seq_h1")
        ],
        dim=1,
    )
    latest_after = torch.cat(
        [
            changed[key][:, -1].reshape(len(changed[key]), -1)
            for key in ("seq", "seq_m5", "seq_m15", "seq_h1")
        ],
        dim=1,
    )

    with torch.no_grad():
        reference = encoder(obs)
        history_changed = encoder(changed)

    torch.testing.assert_close(latest_before, latest_after, rtol=0.0, atol=0.0)
    assert not torch.allclose(reference, history_changed)


def test_tcn_arch_is_the_single_sequence_extractor() -> None:
    assert encoder_for("tcn") is TCNEncoder
    assert encoder_for("mtf") is MTFEncoder
    assert encoder_for("mtf_reasoning") is MTFReasoningEncoder
    assert encoder_for("gru") is GRUEncoder
    assert encoder_for("transformer") is TransformerEncoder


def test_transformer_builds_a_causal_mask_when_runtime_window_exceeds_saved_size() -> None:
    observation_space = spaces.Dict(
        {
            "seq": spaces.Box(-1.0, 1.0, shape=(4, 2), dtype=np.float32),
            "account": spaces.Box(-1.0, 1.0, shape=(6,), dtype=np.float32),
        }
    )
    encoder = TransformerEncoder(
        observation_space=observation_space,
        seq_len=4,
        n_features=2,
        latent_dim=8,
        d_model=8,
        nhead=2,
    )

    mask = encoder._get_mask(6, torch.device("cpu"))

    assert mask.shape == (6, 6)
    assert torch.isneginf(mask[0, 1])
    assert mask[1, 0] == 0.0


def test_extractor_precision_wrapper_skips_transformers_and_existing_wrappers() -> None:
    observation_space = spaces.Dict(
        {
            "seq": spaces.Box(-1.0, 1.0, shape=(4, 2), dtype=np.float32),
            "account": spaces.Box(-1.0, 1.0, shape=(6,), dtype=np.float32),
        }
    )
    transformer = TransformerEncoder(
        observation_space=observation_space,
        seq_len=4,
        n_features=2,
        latent_dim=8,
    )
    original_transformer_forward = cast(Any, transformer.forward).__func__
    encoder_precision.enable_extractor_autocast(transformer, torch.float16)
    assert cast(Any, transformer.forward).__func__ is original_transformer_forward

    identity = nn.Identity()
    original_identity_forward = cast(Any, identity.forward).__func__
    encoder_precision.enable_extractor_autocast(identity, None)
    assert cast(Any, identity.forward).__func__ is original_identity_forward
    cast(Any, identity)._amp_wrapped = True
    encoder_precision.enable_extractor_autocast(identity, torch.float16)
    assert cast(Any, identity.forward).__func__ is original_identity_forward


def test_fp16_autocast_falls_back_to_fp32_for_nonfinite_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = iter([torch.tensor([float("inf")]), torch.tensor([1.0])])

    class RecordingExtractor(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def forward(self, *_args: Any, **_kwargs: Any) -> torch.Tensor:
            self.calls += 1
            return next(outputs)

    monkeypatch.setattr(
        cast(Any, encoder_precision).torch, "autocast", lambda **_kwargs: nullcontext()
    )
    extractor = RecordingExtractor()
    encoder_precision.enable_extractor_autocast(extractor, torch.float16)

    with torch.no_grad():
        result = extractor()

    assert result.dtype == torch.float32
    assert torch.isfinite(result).all()
    assert extractor.calls == 2


def test_autocast_wrapper_rejects_non_tensor_feature_output() -> None:
    class InvalidExtractor(nn.Module):
        def forward(self, *_args: Any, **_kwargs: Any) -> str:
            return "invalid"

    extractor = InvalidExtractor()
    encoder_precision.enable_extractor_autocast(extractor, torch.float16)

    with pytest.raises(TypeError, match="must return a torch.Tensor"):
        extractor()


def test_autocast_inference_rejects_non_tensor_after_autocast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InvalidExtractor(nn.Module):
        def forward(self, *_args: Any, **_kwargs: Any) -> str:
            return "invalid"

    monkeypatch.setattr(
        cast(Any, encoder_precision).torch, "autocast", lambda **_kwargs: nullcontext()
    )
    extractor = InvalidExtractor()
    encoder_precision.enable_extractor_autocast(extractor, torch.bfloat16)

    with torch.no_grad(), pytest.raises(TypeError, match="must return a torch.Tensor"):
        extractor()


@pytest.mark.parametrize(
    ("retry_output", "exception", "message"),
    [
        ("invalid", TypeError, "must return a torch.Tensor"),
        (torch.tensor([float("nan")]), FloatingPointError, "non-finite features"),
    ],
)
def test_fp16_autocast_retry_rejects_invalid_fp32_output(
    monkeypatch: pytest.MonkeyPatch, retry_output: object, exception: type[Exception], message: str
) -> None:
    outputs = iter([torch.tensor([float("inf")]), retry_output])

    class RecordingExtractor(nn.Module):
        def forward(self, *_args: Any, **_kwargs: Any) -> object:
            return next(outputs)

    monkeypatch.setattr(
        cast(Any, encoder_precision).torch, "autocast", lambda **_kwargs: nullcontext()
    )
    extractor = RecordingExtractor()
    encoder_precision.enable_extractor_autocast(extractor, torch.float16)

    with torch.no_grad(), pytest.raises(exception, match=message):
        extractor()


def test_sequence_encoder_account_contract_rejects_missing_or_mismatched_box() -> None:
    with pytest.raises(TypeError, match="Dict observation space"):
        _resolve_account_dim(object(), None)
    with pytest.raises(TypeError, match="Box account vector"):
        _resolve_account_dim(spaces.Dict({"seq": spaces.Box(-1, 1, shape=(4, 2))}), None)
    with pytest.raises(TypeError, match="Box account vector"):
        _resolve_account_dim(spaces.Dict({"account": spaces.Box(-1, 1, shape=(2, 3))}), None)
    account_space = spaces.Dict({"account": spaces.Box(-1, 1, shape=(6,))})
    with pytest.raises(ValueError, match="does not match observation space width 6"):
        _resolve_account_dim(account_space, 5)
    assert _resolve_account_dim(account_space, 6) == 6


def test_valid_lengths_expands_one_dimensional_mask_and_clamps_empty_rows() -> None:
    seq = torch.zeros(3, 4, 2)

    lengths = _valid_lengths(seq, {"seq_mask": torch.tensor([1.0, 1.0, 0.0, 0.0])})
    empty_lengths = _valid_lengths(seq, {"seq_mask": torch.zeros(4)})

    assert lengths.tolist() == [2, 2, 2]
    assert empty_lengths.tolist() == [1, 1, 1]


def test_efficient_mtf_stream_contract_reports_missing_required_streams() -> None:
    observation_space = spaces.Dict(
        {
            "seq": spaces.Box(-1, 1, shape=(4, 2)),
            "seq_mask": spaces.Box(0, 1, shape=(4,)),
        }
    )

    with pytest.raises(ValueError, match="seq_m3 and mask_m3"):
        observation_streams(observation_space)


def test_autocast_precision_remains_inactive_for_none_dtype() -> None:
    extractor = nn.Identity()
    sample = torch.ones((2, 3))
    expected = extractor(sample)

    encoder_precision.enable_extractor_autocast(extractor, None)

    assert torch.equal(extractor(sample), expected)
    assert not getattr(extractor, "_amp_wrapped", False)
