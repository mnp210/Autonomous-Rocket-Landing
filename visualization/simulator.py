"""Interactive flight simulation visualizer and trajectory renderer."""

from typing import Optional
from stable_baselines3 import PPO
from environments.lunar_lander import make_lunar_lander_env


def run_simulation(model_path: Optional[str] = None, episodes: int = 5):
    """Runs and renders the landing environment using trained policy or heuristic baseline."""
    env = make_lunar_lander_env(continuous=True, render_mode="human")
    model = PPO.load(model_path) if model_path else None

    for ep in range(episodes):
        obs, _ = env.reset()
        done = False
        step = 0
        while not done:
            if model:
                action, _ = model.predict(obs, deterministic=True)
            else:
                action = env.action_space.sample()

            obs, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            step += 1

        print(f"Episode {ep + 1} finished in {step} steps.")

    env.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Visualize Rocket Landing Simulation")
    parser.add_argument("--model-path", type=str, default=None, help="Path to trained PPO model")
    parser.add_argument("--episodes", type=int, default=3, help="Number of episodes to simulate")
    args = parser.parse_args()

    run_simulation(model_path=args.model_path, episodes=args.episodes)
