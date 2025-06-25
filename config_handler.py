import yaml
import logging


def read_config(file_name='config.yaml'):
    with open(file_name, 'r') as file:
        return yaml.safe_load(file)

class Config:
    def __init__(self, section_name, file_name='config.yaml'):
        config_data = read_config(file_name)
        self.config = config_data.get(section_name, {})

    def __getitem__(self, key):
        return self.config[key]

    def __getattr__(self, key):
        try:
            return self.config[key]  # Enables config.key
        except KeyError:
            raise AttributeError(f"'Config' object has no attribute '{key}'")

    def as_dict(self):
        return self.config
