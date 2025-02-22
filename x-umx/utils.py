# Copyright (c) 2021 Sony Corporation. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import sklearn.preprocessing
import tqdm
import nnabla as nn
from model import STFT, Spectrogram


def get_nnabla_version_integer():
    from nnabla import __version__
    import re
    r = list(map(int, re.match('^(\d+)\.(\d+)\.(\d+)', __version__).groups()))
    return r[0] * 10000 + r[1] * 100 + r[2]


def get_statistics(args, datasource):
    scaler = sklearn.preprocessing.StandardScaler()
    pbar = tqdm.tqdm(range(len(datasource.mus.tracks)))

    for ind in pbar:
        x = datasource.mus.tracks[ind].audio.T
        audio = nn.NdArray.from_numpy_array(x[None, ...])
        target_spec = Spectrogram(
            *STFT(audio, n_fft=args.nfft, n_hop=args.nhop),
            mono=True
        )
        pbar.set_description("Compute dataset statistics")
        scaler.partial_fit(np.squeeze(target_spec.data))

    # set inital input scaler values
    std = np.maximum(
        scaler.scale_,
        1e-4*np.max(scaler.scale_)
    )
    return scaler.mean_, std


def bandwidth_to_max_bin(sample_rate, n_fft, bandwidth):
    freqs = np.linspace(
        0, float(sample_rate) / 2, n_fft // 2 + 1,
        endpoint=True
    )

    return np.max(np.where(freqs <= bandwidth)[0]) + 1


class AverageMeter(object):
    """Computes and stores the average and current value"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


class EarlyStopping(object):
    def __init__(self, mode='min', min_delta=0, patience=10):
        self.mode = mode
        self.min_delta = min_delta
        self.patience = patience
        self.best = None
        self.num_bad_epochs = 0
        self.is_better = None
        self._init_is_better(mode, min_delta)

        if patience == 0:
            self.is_better = lambda a, b: True

    def step(self, metrics):
        if self.best is None:
            self.best = metrics
            return False

        if np.isnan(metrics):
            return True

        if self.is_better(metrics, self.best):
            self.num_bad_epochs = 0
            self.best = metrics
        else:
            self.num_bad_epochs += 1

        if self.num_bad_epochs >= self.patience:
            return True

        return False

    def _init_is_better(self, mode, min_delta):
        if mode not in {'min', 'max'}:
            raise ValueError('mode ' + mode + ' is unknown!')
        if mode == 'min':
            self.is_better = lambda a, best: a < best - min_delta
        if mode == 'max':
            self.is_better = lambda a, best: a > best + min_delta
