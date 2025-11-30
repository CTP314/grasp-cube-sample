import grasp_cube.agents.robots.so101.so_101
from dataclasses import dataclass
from typing import Annotated, Optional
import tyro
import gymnasium as gym
import mani_skill
from mani_skill.agents.controllers.base_controller import DictController
from mani_skill.envs.sapien_env import BaseEnv
from lerobot.datasets.lerobot_dataset import LeRobotDataset
import pathlib
import json
import numpy as np
import matplotlib.pyplot as plt

@dataclass
class Args:
    repo_id: str = "eai-2025-fall/lift" # actually unused
    episode_index: int | None = None
    root: pathlib.Path | None = None
    
    sim_freq: int = 300
    control_freq: int = 30 # real robot control frequency
    render_mode: str = "human"
    
class SingleArmRealRobotWrapper(gym.Wrapper):
    def __init__(self, env: BaseEnv):
        super().__init__(env)
        self.env: BaseEnv = env.unwrapped
        assert self.env.obs_mode == "state_dict", "this wrapper only supports state observation"
        assert self.env.control_mode == "pd_joint_pos", "this wrapper only supports position control mode"
        
        activate_joints = self.env.agent.robot.active_joints
        sim_joint_names = [j.name for j in activate_joints]
        self.real_joint_ranges = []
        for jn in sim_joint_names:
            if jn == "gripper":
                self.real_joint_ranges.append([0, 100])  # gripper range
            else:
                self.real_joint_ranges.append([-100, 100])  # default range
        self.real_joint_ranges = np.array(self.real_joint_ranges)
        self.sim_joint_ranges = np.concatenate([j.get_limits() for j in activate_joints])
    
    def transform_joint_positions_from_real_to_sim(self, real_qpos: np.ndarray) -> np.ndarray:
        sim_low = self.sim_joint_ranges[:, 0]
        sim_high = self.sim_joint_ranges[:, 1]
        real_low = self.real_joint_ranges[:, 0]
        real_high = self.real_joint_ranges[:, 1]
        if real_qpos.ndim == 2:
            sim_low = sim_low[np.newaxis, :]
            sim_high = sim_high[np.newaxis, :]
            real_low = real_low[np.newaxis, :]
            real_high = real_high[np.newaxis, :]
        
        scaled_qpos = (real_qpos - real_low) / (real_high - real_low) * (sim_high - sim_low) + sim_low
        scaled_qpos = np.clip(scaled_qpos, sim_low, sim_high)
        return scaled_qpos
    
    def transform_joint_positions_from_sim_to_real(self, sim_qpos: np.ndarray) -> np.ndarray:
        sim_low = self.sim_joint_ranges[:, 0]
        sim_high = self.sim_joint_ranges[:, 1]
        real_low = self.real_joint_ranges[:, 0]
        real_high = self.real_joint_ranges[:, 1]
        if sim_qpos.ndim == 2:
            sim_low = sim_low[np.newaxis, :]
            sim_high = sim_high[np.newaxis, :]
            real_low = real_low[np.newaxis, :]
            real_high = real_high[np.newaxis, :]
        
        scaled_qpos = (sim_qpos - sim_low) / (sim_high - sim_low) * (real_high - real_low) + real_low
        scaled_qpos = np.clip(scaled_qpos, real_low, real_high)
        return scaled_qpos

    def process_observation(self, observation: dict) -> dict:
        sim_joint_positions = observation['agent']['qpos']
        real_joint_positions = self.transform_joint_positions_from_sim_to_real(sim_joint_positions)
        observation['extra']['real_qpos'] = real_joint_positions
        return observation        

    def step(self, action: np.ndarray):
        # action is in sim joint space, need to map to real joint space
        sim_action = self.transform_joint_positions_from_real_to_sim(action)
        
        observation, reward, terminated, truncated, info = self.env.step(sim_action)
        return self.process_observation(observation), reward, terminated, truncated, info
    
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        observation, info = self.env.reset(seed=seed, options=options)
        observation = self.process_observation(observation)
        return observation, info
    
    def set_qpos(self, real_qpos: np.ndarray):
        sim_qpos = self.transform_joint_positions_from_real_to_sim(real_qpos)
        self.env.agent.robot.set_qpos(sim_qpos)
        self.env.agent.controller.reset()
    
if __name__ == "__main__":
    args = tyro.cli(Args)
    dataset = LeRobotDataset(
        repo_id=args.repo_id,
        root=args.root,
        episodes=[args.episode_index] if args.episode_index is not None else None, 
    )
    env = gym.make(
        "Empty-v1",
        obs_mode="state_dict",
        control_mode="pd_joint_pos", # only support position control in real robot
        enable_shadow=True,
        robot_uids="so101",
        render_mode=args.render_mode,
        sim_config=dict(sim_freq=args.sim_freq, control_freq=args.control_freq),
    )
    env = SingleArmRealRobotWrapper(env)
    current_episode = -1
    
    real_sim_robot_qpos_log = []
    real_gt_robot_qpos_log = []
    
    for i in range(len(dataset)):
        if dataset[i]['episode_index'] != current_episode:
            env.reset(seed=0)
            env.set_qpos(dataset[i]['observation.state'])
            current_episode = dataset[i]['episode_index']
            
        action = dataset[i]['action']
        observation, reward, terminated, truncated, info = env.step(action)
        env.render()
        
        real_sim_robot_qpos_log.append(observation['extra']['real_qpos'].numpy().copy()[0])
        real_gt_robot_qpos_log.append(dataset[i]['observation.state'].numpy().copy())
        
    real_sim_robot_qpos_log = np.array(real_sim_robot_qpos_log)
    real_gt_robot_qpos_log = np.array(real_gt_robot_qpos_log)
    
    time_steps = np.arange(real_sim_robot_qpos_log.shape[0])
    joint_num = real_sim_robot_qpos_log.shape[1]

    fig, axs = plt.subplots(joint_num, 1, figsize=(8, joint_num * 2), sharex=True)
    axs = np.atleast_1d(axs)

    for j, ax in enumerate(axs):
        ax.plot(time_steps, real_sim_robot_qpos_log[:, j], label='Sim robot', color='blue')
        ax.plot(time_steps, real_gt_robot_qpos_log[:, j], label='Real robot', color='orange', linestyle='--')
        ax.set_ylabel(f'Joint {j} position')
        ax.legend()
        ax.grid(True)

    axs[-1].set_xlabel('Time step')
    plt.tight_layout()
    plt.savefig("robot_qpos_comparison.png", dpi=300)
    plt.close(fig)