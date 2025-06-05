import argparse
import os

from stable_baselines3 import PPO

from bomberman_env import BombermanEnv


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate a trained PPO agent on Bomberman")
    parser.add_argument(
        "--model-path",
        type=str,
        default=os.path.join("rl_ai", "models", "bomberman_ppo.zip"),
        help="Path to the trained model",
    )
    parser.add_argument("--episodes", type=int, default=5, help="Number of episodes to run")
    parser.add_argument("--render", action="store_true", help="Render environment during evaluation")
    parser.add_argument(
        "--ai-archetype", type=str, default=None, help="Opponent AI archetype (optional)"
    )
    return parser.parse_args()


def run_episode(env, model, render: bool) -> float:
    obs, _ = env.reset()
    done = False
    episode_reward = 0.0
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(int(action))
        episode_reward += reward
        done = terminated or truncated
        if render:
            env.render()
    return episode_reward


def main() -> None:
    args = parse_args()
    render_mode = "human" if args.render else None

    env = BombermanEnv(render_mode=render_mode, ai_archetype=args.ai_archetype)
    model = PPO.load(args.model_path)

    rewards = []
    for ep in range(args.episodes):
        reward = run_episode(env, model, args.render)
        rewards.append(reward)
        print(f"Episode {ep + 1}: reward={reward}")

    if rewards:
        avg = sum(rewards) / len(rewards)
        print(f"Average reward over {len(rewards)} episodes: {avg}")

    env.close()


if __name__ == "__main__":
    main()
