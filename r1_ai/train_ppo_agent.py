import argparse
import os

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback

from bomberman_env import BombermanEnv


def parse_args():
    parser = argparse.ArgumentParser(description="Train PPO agent for Bomberman")
    parser.add_argument("--timesteps", type=int, default=100_000,
                        help="Total training timesteps")
    parser.add_argument("--log-dir", type=str, default="rl_ai/tensorboard_logs/",
                        help="TensorBoard log directory")
    parser.add_argument("--model-dir", type=str, default="rl_ai/models/",
                        help="Directory to save models")
    parser.add_argument("--render", action="store_true",
                        help="Render environment during training")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render_mode = "human" if args.render else None

    os.makedirs(args.log_dir, exist_ok=True)
    os.makedirs(args.model_dir, exist_ok=True)

    env = DummyVecEnv([lambda: BombermanEnv(render_mode=render_mode)])

    checkpoint = CheckpointCallback(save_freq=10_000,
                                    save_path=args.model_dir,
                                    name_prefix="checkpoint")

    eval_env = DummyVecEnv([lambda: BombermanEnv(render_mode=None)])
    eval_callback = EvalCallback(eval_env,
                                 best_model_save_path=args.model_dir,
                                 log_path=args.log_dir,
                                 eval_freq=10_000,
                                 n_eval_episodes=5,
                                 deterministic=True,
                                 render=False)

    model = PPO("MlpPolicy", env, verbose=1, tensorboard_log=args.log_dir)

    model.learn(total_timesteps=args.timesteps,
                callback=[checkpoint, eval_callback])

    model.save(os.path.join(args.model_dir, "bomberman_ppo"))

    env.close()
    eval_env.close()


if __name__ == "__main__":
    main()

