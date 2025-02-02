import os
from collections import Counter
from pathlib import Path
from pprint import pprint

import matplotlib.pyplot as plt
import numpy as np
import zarr
from l5kit.configs import load_config_data
from l5kit.data import PERCEPTION_LABELS, ChunkedDataset, LocalDataManager
from l5kit.dataset import AgentDataset, EgoDataset
from l5kit.geometry import transform_points
from l5kit.rasterization import build_rasterizer
from l5kit.visualization import TARGET_POINTS_COLOR, draw_trajectory
from prettytable import PrettyTable
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader
from tqdm.notebook import tqdm

import utils


class LyftLDM(LightningDataModule):
    def __init__(self, args, data_root):
        super().__init__()
        self.args = args
        if args.mode == "train":
            self.cfg = utils.get_train_cfg(args)
        else:
            self.cfg = utils.get_test_cfg(args)
        self.data_root = data_root
        self.dm = LocalDataManager(data_root)
        self.rast = build_rasterizer(self.cfg, self.dm)
        # self.ego_dataset = EgoDataset(self.cfg, self.zarr_dataset, self.rast)

    def chunked_dataset(self, relative_path):
        dataset_path = self.dm.require(relative_path)
        zarr_dataset = ChunkedDataset(dataset_path)
        zarr_dataset.open()
        return zarr_dataset

    def val_dataloader(self):
        zarr_dataset = self.chunked_dataset("scenes/validate.zarr")
        agent_dataset = AgentDataset(self.cfg, zarr_dataset, self.rast)
        return DataLoader(
            agent_dataset,
            shuffle=False,
            batch_size=self.args.batch_size,
            num_workers=self.args.num_workers,
        )

    def test_dataloader(self):
        zarr_dataset = self.chunked_dataset("scenes/test.zarr")
        test_mask = np.load(f"{self.data_root}/scenes/mask.npz")["arr_0"]
        self.agent_dataset = AgentDataset(
            self.cfg, zarr_dataset, self.rast, agents_mask=test_mask
        )
        return DataLoader(
            self.agent_dataset,
            shuffle=False,
            batch_size=self.args.batch_size,
            num_workers=self.args.num_workers,
        )

    def train_dataloader(self):
        zarr_dataset = self.chunked_dataset("scenes/train.zarr")
        self.agent_dataset = AgentDataset(self.cfg, zarr_dataset, self.rast)
        return DataLoader(
            self.agent_dataset,
            shuffle=self.args.shuffle,
            batch_size=self.args.batch_size,
            num_workers=self.args.num_workers,
        )

    def plt_show_agent_map(self, idx):
        data = self.agent_dataset[idx]
        im = data["image"].transpose(1, 2, 0)
        im = self.rast.to_rgb(im)
        target_positions_pixels = transform_points(
            data["target_positions"] + data["centroid"][:2], data["world_to_image"]
        )
        draw_trajectory(
            im, target_positions_pixels, TARGET_POINTS_COLOR, 1,  data["target_yaws"]
        )
        plt.imshow(im[::-1])
        plt.savefig("filename.png")
