import itertools
from typing import Any, Optional

import tensorflow as tf

_EPSILON = tf.keras.backend.epsilon()


def categorical_focal_loss(y_true, y_pred, gamma, *,
                           class_weight: Optional[Any] = None,
                           from_logits: bool = False, axis: int = -1
                           ) -> tf.Tensor:
    # Process focusing parameter
    gamma = tf.convert_to_tensor(gamma, dtype=tf.dtypes.float32)
    gamma_rank = gamma.shape.rank
    scalar_gamma = gamma_rank == 0

    # Process class weight
    if class_weight is not None:
        class_weight = tf.convert_to_tensor(class_weight, dtype=tf.dtypes.float32)

    # Process prediction tensor
    y_pred = tf.convert_to_tensor(y_pred)
    y_pred_rank = y_pred.shape.rank
    if y_pred_rank is not None:
        axis %= y_pred_rank
        if axis != y_pred_rank - 1:
            # Put channel axis last for softmax_cross_entropy_with_logits
            perm = list(itertools.chain(range(axis), range(axis + 1, y_pred_rank), [axis]))
            y_pred = tf.transpose(y_pred, perm=perm)
    elif axis != -1:
        raise ValueError(
            f'Cannot compute categorical focal loss with axis={axis} on '
            'a prediction tensor with statically unknown rank.')
    y_pred_shape = tf.shape(y_pred)

    # Process ground truth tensor (one-hot encode)
    y_true = tf.dtypes.cast(y_true, dtype=tf.dtypes.int64)
    y_true = tf.one_hot(y_true, depth=y_pred_shape[-1])

    xent_loss = tf.nn.softmax_cross_entropy_with_logits(
        labels=y_true,
        logits=y_pred,
    )

    y_true_rank = y_true.shape.rank
    probs = tf.nn.softmax(y_pred, axis=-1)
    if not scalar_gamma:
        gamma = tf.gather(gamma, y_true, axis=0, batch_dims=y_true_rank)
    focal_modulation = (1 - probs) ** gamma
    loss = focal_modulation * xent_loss

    if class_weight is not None:
        class_weight = tf.gather(class_weight, y_true, axis=0, batch_dims=y_true_rank)
        loss *= class_weight

    return loss


@tf.keras.utils.register_keras_serializable()
class CategoricalFocalLoss(tf.keras.losses.Loss):
    def __init__(self, gamma, class_weight: Optional[Any] = None,
                 from_logits: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.gamma = gamma
        self.class_weight = class_weight
        self.from_logits = from_logits

    def get_config(self):
        config = super().get_config()
        config.update(gamma=self.gamma, class_weight=self.class_weight,
                      from_logits=self.from_logits)
        return config

    def call(self, y_true, y_pred):
        return categorical_focal_loss(y_true=y_true, y_pred=y_pred,
                                      class_weight=self.class_weight,
                                      gamma=self.gamma,
                                      from_logits=self.from_logits)
