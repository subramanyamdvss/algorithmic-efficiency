"""MNIST workload parent class."""

import math
import os
from typing import Dict, Iterator, Optional, Tuple
# from algorithmic_efficiency.workloads.mnist.mnist_jax.workload import get_mnist_dataset
from absl import flags
from flax import jax_utils
import jax
import torch
import tensorflow as tf
import tensorflow_datasets as tfds
import torch.distributed as dist
import itertools
from algorithmic_efficiency import spec
import algorithmic_efficiency.random_utils as prng
import functools
from algorithmic_efficiency import data_utils

FLAGS = flags.FLAGS
USE_PYTORCH_DDP = 'LOCAL_RANK' in os.environ


def normalize(image, mean, stddev):
  return (tf.cast(image, tf.float32) - mean) / stddev


def get_mnist_dataset(data_rng: jax.random.PRNGKey,
                      num_train_examples: int,
                      train_mean,
                      train_stddev,
                      split: str,
                      data_dir: str,
                      global_batch_size: int):
  shuffle = split in ['train', 'eval_train']
  if shuffle:
    tfds_split = f'train[:{num_train_examples}]'
  elif split == 'validation':
    tfds_split = f'train[{num_train_examples}:]'
  else:
    tfds_split = 'test'
  ds = tfds.load(
      'mnist:3.0.1', split=tfds_split, shuffle_files=False, data_dir=data_dir)
  ds = ds.map(
      lambda x: {
          'inputs': normalize(x['image'], train_mean, train_stddev),
          'targets': x['label'],
      })
  ds = ds.cache()
  is_train = split == 'train'
  if shuffle:
    ds = ds.shuffle(16 * global_batch_size, seed=data_rng[0])
    if is_train:
      ds = ds.repeat()
  ds = ds.batch(global_batch_size, drop_remainder=is_train)
  ds = map(
      functools.partial(
          data_utils.shard_and_maybe_pad_np,
          global_batch_size=global_batch_size),
      ds)
  return iter(ds)


class BaseMnistWorkload(spec.Workload):

  def has_reached_goal(self, eval_result: Dict[str, float]) -> bool:
    return eval_result['validation/accuracy'] > self.target_value

  @property
  def target_value(self) -> float:
    return 0.9

  @property
  def loss_type(self) -> spec.LossType:
    return spec.LossType.SOFTMAX_CROSS_ENTROPY

  @property
  def num_train_examples(self) -> int:
    return 50000

  @property
  def num_eval_train_examples(self) -> int:
    # Round up from num_validation_examples (which is the default for
    # num_eval_train_examples) to the next multiple of eval_batch_size, so that
    # we don't have to extract the correctly sized subset of the training data.
    rounded_up_multiple = math.ceil(self.num_validation_examples /
                                    self.eval_batch_size)
    return rounded_up_multiple * self.eval_batch_size

  @property
  def num_validation_examples(self) -> int:
    return 10000

  @property
  def num_test_examples(self) -> int:
    return 10000

  @property
  def eval_batch_size(self) -> int:
    return 10000

  @property
  def train_mean(self) -> float:
    return 0.1307

  @property
  def train_stddev(self) -> float:
    return 0.3081

  @property
  def max_allowed_runtime_sec(self) -> int:
    return 60

  @property
  def eval_period_time_sec(self) -> int:
    return 10

  def _build_input_queue(
      self,
      data_rng: spec.RandomState,
      split: str,
      data_dir: str,
      global_batch_size: int,
      cache: Optional[bool] = None,
      repeat_final_dataset: Optional[bool] = None,
      num_batches: Optional[int] = None) -> Iterator[Dict[str, spec.Tensor]]:
    ds = get_mnist_dataset(
        data_rng=data_rng,
        num_train_examples=self.num_train_examples,
        train_mean=self.train_mean,
        train_stddev=self.train_stddev,
        split=split,
        data_dir=data_dir,
        global_batch_size=global_batch_size)

    if split != 'train':
      # Note that this stores the entire eval dataset in memory.
      ds = itertools.cycle(ds)
    return ds

  @property
  def step_hint(self) -> int:
    # Note that the target setting algorithms were not actually run on this
    # workload, but for completeness we provide the number of steps for 10
    # epochs at batch size 64.
    return 7813

  def _eval_model(
      self,
      params: spec.ParameterContainer,
      batch: Dict[str, spec.Tensor],
      model_state: spec.ModelAuxiliaryState,
      rng: spec.RandomState) -> Dict[spec.Tensor, spec.ModelAuxiliaryState]:
    raise NotImplementedError

  def _eval_model_on_split(self,
                           split: str,
                           num_examples: int,
                           global_batch_size: int,
                           params: spec.ParameterContainer,
                           model_state: spec.ModelAuxiliaryState,
                           rng: spec.RandomState,
                           data_dir: str,
                           global_step: int = 0) -> Dict[str, float]:
    """Run a full evaluation of the model."""
    del global_step
    data_rng, model_rng = prng.split(rng, 2)
    if split not in self._eval_iters:
      self._eval_iters[split] = self._build_input_queue(
          data_rng, split, data_dir, global_batch_size=global_batch_size)

    total_metrics = {
        'accuracy': 0.,
        'loss': 0.,
    }
    num_batches = int(math.ceil(num_examples / global_batch_size))
    num_devices = max(torch.cuda.device_count(), jax.local_device_count())
    for _ in range(num_batches):
      batch = next(self._eval_iters[split])
      per_device_model_rngs = prng.split(model_rng, num_devices)
      batch_metrics = self._eval_model(params,
                                       batch,
                                       model_state,
                                       per_device_model_rngs)
      total_metrics = {
          k: v + batch_metrics[k] for k, v in total_metrics.items()
      }
    if FLAGS.framework == 'jax':
      total_metrics = jax_utils.unreplicate(total_metrics)
      return {k: float(v / num_examples) for k, v in total_metrics.items()}
    elif USE_PYTORCH_DDP:
      for metric in total_metrics.values():
        dist.all_reduce(metric)
    return {k: float(v.item() / num_examples) for k, v in total_metrics.items()}
