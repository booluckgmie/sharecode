from taipy.config import Config
from taipy.core import Core
import pandas as pd

# Load your config
Config.load("config.toml")

# Initialize Taipy Core
Core().run() # This starts the Taipy Core service

# Create scenario and run
scenario_cfg = Config.scenarios.default
scenario = scenario_cfg.create_scenario()

# Submit the scenario to run its tasks
Core.submit(scenario)

# Wait for the scenario to complete (optional, but good practice for local execution)
# You might need to add a small loop or a more robust wait mechanism for production
import time
while scenario.get_status().is_running():
    time.sleep(0.1)

# Print result
print("\nService Provider Percentage:")
# Access the data node directly from the scenario's data_nodes
print(scenario.service_perct_output.read())