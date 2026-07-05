from stt.config import load_config
from stt.cli import run


def main():

    cfg = load_config()

    run(cfg)
