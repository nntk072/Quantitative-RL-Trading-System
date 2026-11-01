# Models and learning API

The model and learning APIs separate representation from algorithm and environment semantics. Encoders consume declared observation components; learning adapters construct/train policies and load checkpoints against the declared observation/action schema.

## Core contracts and lifecycle

First define the schema version, field meanings, shapes, and normalization. Implement or select an encoder that maps those inputs to the learner's feature representation. The learner adapter owns PPO/SAC-specific policy construction and checkpoint compatibility. Evaluation and live consumers must validate the same schema before inference; matching tensor dimensions alone does not prove semantic compatibility.

Keep reusable encoders free of trainer-specific assumptions. A schema, architecture, or action-semantics change can invalidate checkpoints even when loading succeeds; document migration or mark the artifact incompatible. A construction smoke proves tensor flow and registration, not policy quality.

## Entry points

Read [models and learning](../../framework/models_and_learning), the [observation/action concepts](../../concepts/observations_and_actions), and the [custom encoder tutorial](../../learn/tutorials/advanced/custom_encoder.ipynb). Generated references: {doc}`models <../generated/models/index>` and {doc}`learning <../generated/learning/index>`.
