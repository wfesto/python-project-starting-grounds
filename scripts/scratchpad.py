import argparse

from ihb_ext.video.info import pymediainfo

# import pymediainfo


def main():
    parser = argparse.ArgumentParser(description="Automatically selects and sets the best subtitle/CC stream as 'default' for supported files.")
    parser.add_argument("-i", "--input", type=str, help="The input path(s) to compare")
    args = parser.parse_args()

    file1 = r""

    file_data = pymediainfo.get_video_metadata(file1)
    print(file_data)


if __name__ == "__main__":
    main()
