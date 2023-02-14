
from unitlab.core import upload_data
import argparse
import os
import errno

def parse_arguments():
    """

    :return:
    """
    parser = argparse.ArgumentParser()
    #parser = argparse.ArgumentParser(
    #    description="Unitlab Inc. python-SDK"
    #)

    parser.add_argument(
        "-k", "--api_key", type=str, nargs="?", help="The api-key that obtained from unitlab.ai", default="", required=True
    )

    parser.add_argument(
        "-t", "--task_id", type=str, nargs="?", help="The task you created in unitlab.ai and want to upload image there", default="", required=True
    )

    parser.add_argument(
        "-i", "--input_dir", type=str, nargs="?", help="The input directory", default="", required=True
    )

    return parser.parse_args()

def main():

    """
    :return:
    """

    args = parse_arguments()

    try:
        os.makedirs(args.input_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    upload_data(args.input_dir, args.api_key, args.task_id)

if __name__ == "__main__":
    main()
