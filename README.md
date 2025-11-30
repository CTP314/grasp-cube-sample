# SO101 Cube Grasping Reference

This repository provides a reference implementation of an SO101 robot arm performing a cube grasping task using [ManiSkill](https://github.com/haosulab/ManiSkill). It includes both reinforcement learning and motion planning based solutions to obtain successful trajectories.

> Note: This project is only tested on Linux. On non-Linux systems, basic GUI visualization and scene preview may still work, but some features will be limited:
> - **Motion Planning**: The current motion planning library is not compatible with other platforms. You may need to replace parts of the code with a motion planning library that supports your OS.
> - **RL Parallelism**: On non-Linux systems, Python multiprocessing may not work as expected. You may need to adjust the parallelization strategy yourself. The reference code uses TDMPC2, which typically runs with a relatively small number of parallel environments (e.g. 32), so it is possible to train purely on CPU.

## Important Update

It is recommended to run uv sync each time you pull updates from GitHub.

Since the LeRobot version has undergone significant changes, we provide a LeRobot branch used by the TAs and have updated the reference for using the LeRobot dataset.

We provide an updated URDF under [`grasp_cube/assets/robots/so101/so101_new`](grasp_cube/assets/robots/so101/so101_new) to address several issues:

- Fixes mirroring issues from the earlier [`so101_old`](grasp_cube/assets/robots/so101/so101_old), making it consistent with the real robot.
- Improves the gripper collision meshes to make grasping easier.
- Refines the inertia of some links to make the simulation more stable.
- Adds two auxiliary links near the gripper fingertips for computing the TCP (Tool Center Point), which is useful for motion planning.

## Installation

From the repo root:

```bash
uv sync
```

If you want to run RL training, install the RL-specific dependencies:

```bash
uv pip install -r rl/tdmpc2/requirements.txt
```

If you want to run LeRobot example, install the dependencies:

```
git submodule update --init --recursive
cd external/lerobot
uv pip install -e .
```

## Getting Started

### Robot Model

The SO101 robot is registered and imported in [`grasp_cube/agents/robots/so101/so_101.py`](grasp_cube/agents/robots/so101/so_101.py). For details on adding custom robots to ManiSkill, see the official tutorial: [Custom Robots](https://maniskill.readthedocs.io/en/latest/user_guide/tutorials/custom_robots.html).

To preview the SO101 robot imported into ManiSkill:

```bash
uv run hello_robot.py
```

Expected preview:

![hello_robot](assets/hello_robot.png)

The green and red spheres attached to the end-effector are the auxiliary links mentioned above for TCP computation. You can remove them by commenting out the corresponding links in the URDF.

### Task Definition

The cube picking task for SO101 is defined in [`grasp_cube/envs/tasks/pick_cube_so101.py`](grasp_cube/envs/tasks/pick_cube_so101.py). For how tasks are structured in ManiSkill, see the [Tasks](https://maniskill.readthedocs.io/en/latest/contributing/tasks.html) tutorial.

To preview the `PickCubeSO101` task:

```bash
uv run hello_pick_cube.py
```

Expected preview:

![hello_pick_cube](assets/hello_pick_cube.png)

- The **blue** thin box shows the cube spawn region.
- The **green** opaque sphere is the goal position.
- The **red** cube and the **green** goal are randomly sampled inside the blue region.
- The goal of the task is for the robot to move the red cube to the green goal position, while maintaining a stable grasp and keeping the arm static.

The size and visualization of the blue region (and other task parameters) can be adjusted or disabled directly in [`grasp_cube/envs/tasks/pick_cube_so101.py`](grasp_cube/envs/tasks/pick_cube_so101.py).

## Motion Planning

We implement a basic motion planner in [`grasp_cube/motionplanning/base_motionplanner`](grasp_cube/motionplanning/base_motionplanner). It takes as input a desired end-effector pose and outputs a sequence of waypoints (a path) for the end-effector.

A concrete solution for the `PickCubeSO101` environment is implemented in [`grasp_cube/motionplanning/so101/solutions/pick_cube.py`](grasp_cube/motionplanning/so101/solutions/pick_cube.py).

To run motion planning for 100 episodes:

```bash
uv run -m grasp_cube.motionplanning.so101.run -n 100
```

You should see output similar to:

```text
proc_id: 0: 100%|█| 100/100 [00:27<00:00,  3.62it/s, success_rate=0.56, failed_motion_plan_rate=0.284, avg_episode_length=97.7...
```

The corresponding trajectories will be saved as HDF5 files under the `demos` directory.

To visualize the motion planning process during data collection, add the `--vis` flag:

```bash
uv run -m grasp_cube.motionplanning.so101.run -n 100 --vis
```

Example visualization:

![motionplanning](assets/motionplanning.png)

This includes visualizations of the target gripper poses. For more configuration options, see [`grasp_cube/motionplanning/so101/run.py`](grasp_cube/motionplanning/so101/run.py).

## Reinforcement Learning

### TDMPC2

We use **TDMPC2**, a model-based RL algorithm with high sample efficiency.

To train a state-based RL policy on `PickCubeSO101-v1`:

```bash
cd rl/tdmpc2
uv run train.py env_id=PickCubeSO101-v1
```

A typical final training log might look like:

```text
eval    E: 19,968       I: 1,000,000    R: 30.16        S: 1.00         T: 6:55:02 
train   E: 19,968       I: 1,000,000    R: 30.19        S: 0.94         T: 6:55:02 
```

Example learned behavior:

![rl.gif](assets/rl.gif)

These results were obtained on an RTX 4090 Laptop GPU, with GPU memory usage under 5 GB.

Some rough time milestones (for reference, may vary by machine):

- First non-zero success rate around `E ≈ 400`, `I ≈ 20k`, about **10 minutes** of training.
- Success rate stabilizing above 80% around `E ≈ 4000`, `I ≈ 200k`, about **80 minutes** of training.

## LeRobot Dataset

Download the dataset from Web Learning to your local machine and run the official LeRobot dataset visualization tool:

```
lerobot-dataset-viz \
    --repo-id eai/lift \
    --root ./datasets/lift \
    --mode local \
    --episode-index 0
```

An example output is shown below:

![lerobot\_dataviz](assets/lerobot_dataviz.png)

Running `hello_real_robot.py` allows you to replay real-world trajectories in simulation and outputs the differences between the simulation and the real world. You can use `--help` to see all available commands:

```
uv run hello_real_robot.py --root ./datasets/lift --episode-index 0
```

Example result:

![sim\_vs\_real](assets/robot_qpos_comparison.png)

## Acknowledgement

Most of this codebase is adapted from or inspired by the official ManiSkill repository.
