# Copyright (c) 2021-2022, InterDigital Communications, Inc
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted (subject to the limitations in the disclaimer
# below) provided that the following conditions are met:

# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * Neither the name of InterDigital Communications, Inc nor the names of its
#   contributors may be used to endorse or promote products derived from this
#   software without specific prior written permission.

# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import annotations

import os
from types import ModuleType
from typing import cast

import compressai
import pandas as pd
from catalyst import dl, metrics
from catalyst.typing import TorchCriterion, TorchOptimizer
from compressai.models.base import CompressionModel
from torch.nn.parallel import DataParallel, DistributedDataParallel

import compressai_train
from compressai_train.plot import plot_rd
from compressai_train.utils.utils import compressai_dataframe, num_parameters


class BaseRunner(dl.Runner):
    criterion: TorchCriterion
    model: CompressionModel | DataParallel | DistributedDataParallel
    optimizer: dict[str, TorchOptimizer]
    batch_meters: dict[str, metrics.IMetric]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_experiment_start(self, runner):
        super().on_experiment_start(runner)
        self._log_git_diff(compressai)
        self._log_git_diff(compressai_train)
        self._log_pip()
        self._log_stats()

    def on_epoch_start(self, runner):
        super().on_epoch_start(runner)

    def on_loader_start(self, runner):
        super().on_loader_start(runner)
        if self.is_infer_loader:
            self.model_module.update()
        self.batch_meters = {}

    def on_loader_end(self, runner):
        for key in self.batch_meters.keys():
            self.loader_metrics[key] = self.batch_meters[key].compute()[0]
        super().on_loader_end(runner)

    def on_epoch_end(self, runner):
        self.epoch_metrics["_epoch_"]["epoch"] = self.epoch_step
        super().on_epoch_end(runner)

    def on_experiment_end(self, runner):
        super().on_experiment_end(runner)

    def log_distribution(self, *args, **kwargs) -> None:
        """Logs distribution to available loggers."""
        for logger in self.loggers.values():
            if not hasattr(logger, "log_distribution"):
                continue
            logger.log_distribution(*args, **kwargs, runner=self)  # type: ignore

    def log_figure(self, *args, **kwargs) -> None:
        """Logs figure to available loggers."""
        for logger in self.loggers.values():
            if not hasattr(logger, "log_figure"):
                continue
            logger.log_figure(*args, **kwargs, runner=self)  # type: ignore

    @property
    def model_module(self) -> CompressionModel:
        """Returns model instance."""
        if isinstance(self.model, (DataParallel, DistributedDataParallel)):
            return cast(CompressionModel, self.model.module)
        return self.model

    @property
    def _current_dataframe(self):
        r = lambda x: float(f"{x:.4g}")
        d = dict(
            name=self.hparams["model"]["name"] + "*",
            epoch=self.epoch_step,
            loss=r(self.loader_metrics["loss"]),
            bpp=r(self.loader_metrics["bpp"]),
            psnr=r(self.loader_metrics["psnr"]),
        )
        return pd.DataFrame.from_dict([d])

    def _current_rd_traces(self):
        return []

    def _update_batch_metrics(self, batch_metrics):
        self.batch_metrics.update(batch_metrics)
        for key in batch_metrics.keys():
            if key not in self.batch_meters:
                continue
            self.batch_meters[key].update(
                _coerce_item(self.batch_metrics[key]),
                self.batch_size,
            )

    def _log_src_artifact(self, tag: str, filename: str):
        src_root = self.hparams["paths"]["src"]
        dest_path = os.path.join(src_root, filename)
        self.log_artifact(tag, path_to_artifact=dest_path)

    def _log_pip(self):
        self._log_src_artifact("pip_list.txt", "pip_list.txt")
        self._log_src_artifact("requirements.txt", "requirements.txt")

    def _log_git_diff(self, package: ModuleType):
        self._log_src_artifact(
            f"{package.__name__}_git_diff", f"{package.__name__}.patch"
        )

    def _log_rd_figure(self, codecs: list[str], dataset: str, **kwargs):
        hover_data = kwargs.get("scatter_kwargs", {}).get("hover_data", [])
        dfs = [compressai_dataframe(name, dataset=dataset) for name in codecs]
        dfs.append(self._current_dataframe)
        df = pd.concat(dfs)
        df = _reorder_dataframe_columns(df, hover_data)
        fig = plot_rd(df, **kwargs)
        for trace in self._current_rd_traces():
            fig.add_trace(trace)
        self.log_figure(f"rd-curves-{dataset}-psnr", fig)

    def _log_stats(self):
        stats = {
            "num_params": num_parameters(self.model),
        }
        self.log_hparams({"stats": stats})


def _coerce_item(x):
    return x.item() if hasattr(x, "item") else x


def _reorder_dataframe_columns(df: pd.DataFrame, head: list[str]) -> pd.DataFrame:
    head_set = set(head)
    columns = head + [x for x in df.columns if x not in head_set]
    return cast(pd.DataFrame, df[columns])
