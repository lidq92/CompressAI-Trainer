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

from typing import Any

import catalyst
import catalyst.callbacks
import catalyst.utils
import hydra
from omegaconf import DictConfig

from compressai_train.config import (
    configure_engine,
    create_criterion,
    create_dataloaders,
    create_model,
    create_optimizer,
    create_scheduler,
    get_env,
    write_config,
)
from compressai_train.runners import ImageCompressionRunner


def setup(conf: DictConfig) -> dict[str, Any]:
    catalyst.utils.set_global_seed(conf.misc.seed)
    catalyst.utils.prepare_cudnn(benchmark=True)

    conf.env = get_env(conf)
    write_config(conf)

    model = create_model(conf)
    criterion = create_criterion(conf.criterion)
    optimizer = create_optimizer(conf.optimizer, model)
    scheduler = create_scheduler(conf.scheduler, optimizer)
    loaders = create_dataloaders(conf)

    d = dict(
        model=model,
        criterion=criterion,
        optimizer=optimizer,
        scheduler=scheduler,
        loaders=loaders,
    )

    return {**d, **configure_engine(conf)}


@hydra.main(version_base=None)
def main(conf: DictConfig):
    engine_kwargs = setup(conf)
    runner = ImageCompressionRunner()
    runner.train(**engine_kwargs)


if __name__ == "__main__":
    main()
