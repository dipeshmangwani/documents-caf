import os
import argparse
import shutil
import modules.pdfProcessor as pdfProcessor


def get_files(src):
    files = []
    for root, directories, filenames in os.walk(src):
        for f in filenames:
            if f.endswith(".pdf"):
                files.append((f[0:-4], root.replace(src, "").lstrip("/"), os.path.join(root, f)))
    return files


def process_file(item, dst, overwrite):
    filename, dirs, src = item
    dst_dir = os.path.join(dst, dirs, filename)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    dst_file = os.path.join(dst_dir, filename + ".pdf")
    if os.path.exists(os.path.join(dst_dir, filename + ".json")) and not overwrite:
        return False
    shutil.copy(src, dst_file)
    status, message = pdfProcessor.parse(filename, dst_dir, overwrite)
    if not status:
        raise Exception(message)
    return status


def run(args):
    src = args.src
    if not os.path.exists(src):
        raise Exception("Source directory %s does not exist" % src)
    dst = args.dst
    if not os.path.exists(dst):
        os.makedirs(dst, exist_ok=True)
    overwrite = args.overwrite
    overwrite = True if overwrite == "y" else False
    files = get_files(src)
    print("Found %d PDF files in %s" % (len(files), src))
    for f in files:
        print("Processing %s" % f[-1], "-In Progress")
        status = process_file(f, dst, overwrite)
        if status:
            print("Processing %s" % f[-1], "-Complete")


if __name__ == '__main__':
    flags = argparse.ArgumentParser("Command line arguments for Document Processing")
    flags.add_argument("-src", type=str, required=True, help="Source directory of files")
    flags.add_argument("-dst", type=str, required=True, help="Destination directory")
    flags.add_argument("-overwrite", type=str, choices=["y", "n"], default="n", help="Overwrite files")
    args = flags.parse_args()
    try:
        run(args)
    except Exception as e:
        print(str(e))