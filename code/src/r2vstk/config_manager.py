import argparse
import logging
import os
import os.path as osp
import random
import numpy as np

from config_parser import parse_config


class ConfigManager:
    """
    Config manager makes various configurations available to all modules.
    """

    def __init__(self):
        """
        Initialize config manager.
        """
        self.args = None  # Contains command line arguments passed in.
        self.room_types = None  # List of supported room types.
        self.data_paths = None  # Configuration of paths to useful data.
        self.arch_defaults = None  # Configuration used to generate scene.json files
        self.parser_config = None  # Configuration used to parsing of r2v output/annotation.
        self.output_path = None  # Output path to store results of the script.
        self.seed = None  # Random seed used.

    def setup_seed(self, seed) -> None:
        """
        Update random seed.
        :param seed: New seed.
        """
        self.seed = seed
        np.random.seed(seed)
        random.seed(seed)
        logging.info("Using seed: %d" % seed)

    def load_default_args(self) -> None:
        """
        Load default arguments. Useful for loading plan2scene in a jupyter notebook.
        """
        parser = argparse.ArgumentParser()
        self.add_args(parser)
        args, _ = parser.parse_known_args()
        self.process_args(args)

    def process_args(self, args, output_is_dir=False) -> None:
        """
        Process command line arguments.
        :param args: Command line arguments.
        :param output_is_dir: Specify true to create a directory at the output path. A log fill will be created automatically in this directory.
        """
        self.args = args
        if "output_path" in self.args.__dict__:
            if isinstance(self.args.output_path, str):
                self.output_path = self.args.output_path
            else:
                self.output_path = self.args.output_path[0]
            if output_is_dir:
                if not osp.exists(self.output_path):
                    os.makedirs(self.output_path)
                logging.basicConfig(level=logging.getLevelName(args.log_level), handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(osp.join(self.output_path, "log.out"))])
            else:
                logging.basicConfig(level=logging.getLevelName(args.log_level))
        else:
            logging.basicConfig(level=logging.getLevelName(args.log_level))

        self.setup_seed(int(args.seed))
        self.data_paths = parse_config(args.data_paths)
        self.parser_config = parse_config(args.parser_config)
        self.arch_defaults = parse_config(args.arch_defaults)
        self.room_types = parse_config(osp.join(args.labels_path, "room_types.json"))
        logging.info("Args: %s" % str(self.args))

    def add_args(self, parser: argparse.ArgumentParser) -> None:
        """
        Add optional arguments to an argument parser.
        :param parser: Argument parser.
        """
        parser.add_argument("--seed", help="Default seed value to use.", default=12415, type=int)
        parser.add_argument("--data-paths", help="Path to data_paths.json file",
                            default="./conf/r2v_importer/data_paths.json")
        parser.add_argument("--parser-config", help="Path to parser_config.json file",
                            default="./conf/r2v_importer/parser_config.json")
        parser.add_argument("--arch-defaults", help="Path to arch_defaults.json file",
                            default="./conf/r2v_importer/arch_defaults.json")
        parser.add_argument("--labels-path", help="Path to directory which contains room_types.json",
                            default="./conf/r2v_importer/labels")
        parser.add_argument("-l", "--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                            default="INFO",
                            help="Set the log level")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="R2V Importer Config Manager")
    conf = ConfigManager()
    conf.add_args(parser)
    args = parser.parse_args()
    conf.process_args(args)

    print(conf)
