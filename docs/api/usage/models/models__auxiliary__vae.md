# Models · `auxiliary.vae`

This page contains 5 public callable records owned by `models.auxiliary.vae`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `VAE`

**Kind:** class · **Status:** stable · **Owner:** `models.auxiliary.vae`

**Purpose:** Variational Autoencoder for full-day narrative embedding.

**Exact API:** {py:obj}`models.auxiliary.vae.VAE` · **Source:** [models/auxiliary/vae.py:250](../../../../models/auxiliary/vae.py#L250)

**Inputs and outputs:**

- **Args:**

  ```text
  seq_len (int): Length of the sequence (number of 5-minute bars)
  n_features (int): Number of features per bar (OHLCV = 5)
  latent_dim (int): Dimension of the latent space (default: 16)
  encoder_channels (tuple[int, ...]): Channels for encoder CNN layers
  decoder_channels (tuple[int, ...]): Channels for decoder CNN layers
  kernel_size (int): Kernel size for CNN layers
  stride (int): Stride for CNN layers
  ```

**Observed usage:**

1. [test fixture: `test_vae_encode_decode`](../../../../tests/unit/models/test_vae.py#L97)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        seq_len = 186
        n_features = 5
        latent_dim = 16

        vae = VAE(
            seq_len=seq_len,
            n_features=n_features,
            latent_dim=latent_dim,
            encoder_channels=(64, 32, 16),
            decoder_channels=(16, 32, 64),
            kernel_size=3,
            stride=2,
        )

        x = torch.randn(4, seq_len, n_features)

        # Test encode
        mu, log_var = vae.encode(x)
# … caller assertions omitted …
```

2. [test fixture: `test_vae_forward`](../../../../tests/unit/models/test_vae.py#L121)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_vae_forward(self) -> None:
    vae = VAE(seq_len=186, n_features=5, latent_dim=16)
    x = torch.randn(4, 186, 5)

    x_recon, mu, log_var = vae(x)

    assert x_recon.shape == (4, 186, 5)
    assert mu.shape == (4, 16)
    assert log_var.shape == (4, 16)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `VAE.decode`

**Kind:** method · **Status:** stable · **Owner:** `models.auxiliary.vae`

**Purpose:** Decode latent vector to reconstructed sequence.

**Exact API:** {py:obj}`models.auxiliary.vae.VAE.decode` · **Source:** [models/auxiliary/vae.py:327](../../../../models/auxiliary/vae.py#L327)

**Inputs and outputs:**

- **Args:**

  ```text
  z (torch.Tensor): Latent vector of shape (batch_size, latent_dim)
  ```

- **Returns:**

  ```text
  torch.Tensor: Reconstructed sequence of shape (batch_size, seq_len, n_features)
  ```

**Observed usage:**

1. [test fixture: `test_vae_encode_decode`](../../../../tests/unit/models/test_vae.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        assert mu.shape == (4, latent_dim)
        assert log_var.shape == (4, latent_dim)

        # Test decode
        z = torch.randn(4, latent_dim)
        x_recon = vae.decode(z)
        assert x_recon.shape == (4, seq_len, n_features)
```

2. [production caller: `forward`](../../../../models/auxiliary/vae.py#L368)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    mu: torch.Tensor
    log_var: torch.Tensor
    mu, log_var = self.encode(x)
    z: torch.Tensor = self.reparameterize(mu, log_var)
    x_recon: torch.Tensor = self.decode(z)
    return x_recon, mu, log_var
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `VAE.encode`

**Kind:** method · **Status:** stable · **Owner:** `models.auxiliary.vae`

**Purpose:** Encode input sequence to latent distribution parameters.

**Exact API:** {py:obj}`models.auxiliary.vae.VAE.encode` · **Source:** [models/auxiliary/vae.py:312](../../../../models/auxiliary/vae.py#L312)

**Inputs and outputs:**

- **Args:**

  ```text
  x (torch.Tensor): Input sequence of shape (batch_size, seq_len, n_features)
  ```

- **Returns:**

  ```text
  torch.Tensor: Mean of latent distribution, shape (batch_size, latent_dim)
  torch.Tensor: Log-variance of latent distribution, shape (batch_size, latent_dim)
  ```

**Observed usage:**

1. [test fixture: `test_vae_encode_decode`](../../../../tests/unit/models/test_vae.py#L110)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        )

        x = torch.randn(4, seq_len, n_features)

        # Test encode
        mu, log_var = vae.encode(x)
        assert mu.shape == (4, latent_dim)
        assert log_var.shape == (4, latent_dim)

        # Test decode
        z = torch.randn(4, latent_dim)
# … caller assertions omitted …
```

2. [test fixture: `test_load_vae_roundtrip`](../../../../tests/unit/models/test_vae_wiring.py#L48)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_load_vae_roundtrip(tmp_path: Path) -> None:
    model = VAE(seq_len=186, n_features=5, latent_dim=16)
    path = tmp_path / "vae.pth"
    torch.save(model.state_dict(), path)
    loaded = load_vae_from_checkpoint(path)
    x = torch.randn(2, 186, 5)
    with torch.no_grad():
        mu_a, _ = model.encode(x)
        mu_b, _ = loaded.encode(x)
    assert torch.allclose(mu_a, mu_b)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `VAE.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.auxiliary.vae`

**Purpose:** Forward pass through VAE.

**Exact API:** {py:obj}`models.auxiliary.vae.VAE.forward` · **Source:** [models/auxiliary/vae.py:353](../../../../models/auxiliary/vae.py#L353)

**Inputs and outputs:**

- **Args:**

  ```text
  x (torch.Tensor): Input sequence of shape (batch_size, seq_len, n_features)
  ```

- **Returns:**

  ```text
  torch.Tensor: Reconstructed sequence, shape (batch_size, seq_len, n_features)
  torch.Tensor: Mean of latent distribution, shape (batch_size, latent_dim)
  torch.Tensor: Log-variance of latent distribution, shape (batch_size, latent_dim)
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = VAE(...)
result = instance.forward(x=...)
```

**Lifecycle context:** This callable participates in `VAE`: Variational Autoencoder for full-day narrative embedding. Related public lifecycle methods: {py:obj}`models.auxiliary.vae.VAE.encode`, {py:obj}`models.auxiliary.vae.VAE.decode`, {py:obj}`models.auxiliary.vae.VAE.reparameterize`, {py:obj}`models.auxiliary.vae.VAE.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `VAE.reparameterize`

**Kind:** method · **Status:** stable · **Owner:** `models.auxiliary.vae`

**Purpose:** Reparameterization trick for sampling from latent distribution.

**Exact API:** {py:obj}`models.auxiliary.vae.VAE.reparameterize` · **Source:** [models/auxiliary/vae.py:339](../../../../models/auxiliary/vae.py#L339)

**Inputs and outputs:**

- **Args:**

  ```text
  mu (torch.Tensor): Mean of latent distribution, shape (batch_size, latent_dim)
  log_var (torch.Tensor): Log-variance of latent distribution, shape (batch_size, latent_dim)
  ```

- **Returns:**

  ```text
  torch.Tensor: Sampled latent vector, shape (batch_size, latent_dim)
  ```

**Observed usage:**

1. [test fixture: `test_vae_reparameterize`](../../../../tests/unit/models/test_vae.py#L137)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_vae_reparameterize(self) -> None:
    vae = VAE(seq_len=186, n_features=5, latent_dim=16)

    mu = torch.randn(4, 16)
    log_var = torch.randn(4, 16)

    z = vae.reparameterize(mu, log_var)

    assert z.shape == (4, 16)
    assert isinstance(z, torch.Tensor)
```

2. [test fixture: `test_vae_reparameterization_differs`](../../../../tests/unit/models/test_vae.py#L178)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_vae_reparameterization_differs(self) -> None:
    vae = VAE(seq_len=186, n_features=5, latent_dim=16)

    mu1 = torch.zeros(4, 16)
    log_var1 = torch.zeros(4, 16)
    mu2 = torch.ones(4, 16)
    log_var2 = torch.zeros(4, 16)

    z1 = vae.reparameterize(mu1, log_var1)
    z2 = vae.reparameterize(mu2, log_var2)

    assert not torch.allclose(z1, z2), "Different latents should yield different z"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
