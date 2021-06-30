import logging
from r2vstk.config_manager import ConfigManager
from r2vstk.house import House
import argparse
import os.path
import json


def run(conf: ConfigManager, source, output_path, scale_factor, save_previews,
        save_room_json, skip_objects=False, adjust_short_walls=False,
        classify_doors_and_windows=False, skip_rdr=False, r2v_annot=False):
    """
    Converts Raster-to-Vector output/annotation to scene.json format.
    """

    house = House()

    # Pass in the scale factor
    house.multiplication_factor = scale_factor

    if r2v_annot:
        # User has provided a r2v annotation file
        house.load_r2v_annot_file(source)
    else:
        # User has provided a r2v output file
        house.load_r2v_output_file(conf, source)

    # Split walls that intersect with other walls into separate wall segments.
    if conf.parser_config.split_walls.enabled:
        house.split_source_walls(conf)

    # Generate wall linkage graph and detect rooms.
    house.generate_wall_graph(conf)

    # Axis align nearly axis aligned walls.
    if conf.parser_config.straighten_walls.enabled:
        house.straighten_walls(conf)

    # Assign annotation AABBs to rooms
    house.populate_room_annotations(conf)

    # Parse object annotation AABBs
    if not skip_objects:
        house.populate_object_annotations(conf)

    # Separate doors from windows.
    if classify_doors_and_windows:
        house.classify_doors_and_windows()

    # Populate additional details related to rooms such as room_id and room_type labels.
    if r2v_annot:
        house.populate_room_descriptions_from_r2v_annot(conf)
    else:
        house.populate_room_descriptions_from_r2v_output()

    # Compute room-door-room connectivity graph edges
    if not skip_rdr:
        house.compute_rdr()

    # Save preview sketches
    if save_previews:
        house.sketch_raw_annotations(conf, os.path.join(output_path, "raw_annot.png"))
        logging.info("Saved {file}".format(file=os.path.join(output_path, "raw_annot.png")))

        # Save wall mask
        wall_mask = house.get_wall_mask()
        with open(os.path.join(output_path, "wall_mask.svg"), 'w') as f:
            f.write(wall_mask._repr_svg_())

    # Save room level results
    for i, room_key in enumerate(house.ordered_rooms):
        if save_previews:
            house.sketch_room_annotations(conf, room_key, os.path.join(output_path, "room_" + str(i) + ".png"))
            logging.info("Saved {file}".format(file=os.path.join(output_path, "room_" + str(i) + ".png")))

        if save_room_json:
            room_json = house.get_room_json(conf, room_key, True, [], adjust_short_walls=adjust_short_walls)[0]

            with open(os.path.join(output_path, room_json["id"] + ".arch.json"), "w") as f:
                f.write(json.dumps(room_json, indent=3))
            logging.info("Saved {file}".format(file=os.path.join(output_path, "room_" + str(i) + ".json")))

    # Save scene.json
    scene_json = house.get_scene_json(conf, adjust_short_walls=adjust_short_walls)
    save_path = os.path.join(output_path, scene_json["scene"]["arch"]["id"] + ".scene.json")
    with open(save_path, "w") as f:
        f.write(json.dumps(scene_json, indent=3))
    logging.info("Saved {file}".format(file=save_path))

    # Save objectaabb.json
    object_aabb_json = house.get_objectaabb_json(conf)
    save_path = os.path.join(output_path, scene_json["scene"]["arch"]["id"] + ".objectaabb.json")
    with open(save_path, "w") as f:
        f.write(json.dumps(object_aabb_json, indent=3))

    logging.info("Saved {file}".format(file=save_path))
    return house


def run_args(conf: ConfigManager, args):
    """
    Process command line args.
    :param conf: ConfigManager
    :param args: Command line args
    """
    if not args.r2v_annot:
        assert conf.room_types is not None

    house = run(conf=conf, source=args.source[0], output_path=args.output_path[0], save_previews=not args.no_previews, save_room_json=args.room_json,
                scale_factor=args.scale_factor[0], skip_objects=args.skip_objects,
                adjust_short_walls=not args.do_not_adjust_short_walls,
                classify_doors_and_windows=not args.do_not_classify_doors_and_windows,
                skip_rdr=args.skip_rdr, r2v_annot=args.r2v_annot)

    return house


def add_args(parser: argparse.ArgumentParser) -> None:
    """
    Add command line args to the parser.
    :param parser: Argument Parser
    """
    parser.add_argument('output_path', metavar='output', type=str, nargs=1,
                        help='directory to save outputs from dataset')
    parser.add_argument('source', metavar='source', type=str, nargs=1,
                        help='path to annotation file from dataset')
    parser.add_argument("--r2v-annot", default=False, action="store_true",
                        help="Process a Raster-to-vector annotation file instead of R2V output file.")
    parser.add_argument("--scale-factor", metavar="mf", type=float, nargs=1, default=[-1],
                        help="Scale factor to multiply all coordinates in the XY plane.")

    parser.add_argument("--no-previews", default=False, action="store_true",
                        help="Don't generate PNG previews")

    parser.add_argument("--room-json", default=False, action="store_true",
                        help="Generate individual room's json")

    parser.add_argument("--skip-objects", default=False, action="store_true",
                        help="Don't place objects")

    parser.add_argument("--do-not-adjust-short-walls", default=False, action="store_true",
                        help="Don't adjust height of short walls such as balconies")
    parser.add_argument("--do-not-classify-doors-and-windows", default=False, action="store_true",
                        help="Don't classify holes as doors or windows")
    parser.add_argument("--skip-rdr", default=False, action="store_true", help="Avoid computing RDR edges.")


if __name__ == "__main__":
    conf = ConfigManager()
    parser = argparse.ArgumentParser(description='Generate scene-toolkit compatible json files.')
    conf.add_args(parser)
    add_args(parser)
    args = parser.parse_args()
    conf.process_args(args, output_is_dir=True)
    run_args(conf, args)
