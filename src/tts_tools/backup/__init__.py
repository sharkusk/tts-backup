from tts_tools.libtts import get_fs_path
from tts_tools.libtts import GAMEDATA_DEFAULT
from tts_tools.libtts import IllegalSavegameException
from tts_tools.libtts import urls_from_save
from tts_tools.libtts import get_save_name
from tts_tools.libtts import recodeURL
from tts_tools.util import print_err
from tts_tools.util import ZipFile
from tts_tools.util import make_safe_filename
from tts_tools.util import save_modification_time
from tts_tools.util import get_mods_in_directory
from tts_tools.util import PrintStatus

import os
import re
import sys
import glob

from alive_progress import alive_bar; import time, logging
from contextlib import nullcontext

def backup_json(
    infile_name,
    out_dir,
    outfile_name,
    comment='',
    dry_run=False,
    gamedata_dir=GAMEDATA_DEFAULT,
    ignore_missing=False,
    deflate=False,
    verbose=False,
):
    try:
        save_name = get_save_name(infile_name)
    except Exception:
        save_name = "???"

    readable_filename = f"{os.path.basename(infile_name)} [{save_name}]"

    if verbose:
        print(readable_filename)

    try:
        urls = urls_from_save(infile_name)
    except (FileNotFoundError, IllegalSavegameException) as error:
        errmsg = "Could not read URLs from '{file}': {error}".format(
            file=infile_name, error=error
        )
        print_err(errmsg)
        sys.exit(1)

    # Change working dir, since get_fs_path gives us a relative path.
    try:
        os.chdir(gamedata_dir)
    except FileNotFoundError as error:
        errmsg = "Could not open gamedata directory '{dir}': {error}".format(
            dir=gamedata_dir, error=error
        )
        print_err(errmsg)
        sys.exit(1)

    # We want to use the absolute filepath
    if outfile_name:
        outfile_name = os.path.join(out_dir, outfile_name)
    else:
        try:
            outfile_basename = get_save_name(infile_name)
            # Make the filename safe (i.e. remove crazy characters)
            outfile_basename = make_safe_filename(outfile_basename)
        except Exception:
            outfile_basename = re.sub(
                r"\.json$", "", os.path.basename(infile_name)
            )
        outfile_name = f"{os.path.join(out_dir, outfile_basename)} [{os.path.splitext(os.path.basename(infile_name))[0]}].zip"

    urls = list(urls)
    with alive_bar(len(urls), dual_line=True, title=readable_filename, unit=' files') if not verbose else nullcontext() as bar:
        ps = PrintStatus(bar)
        try:
            zipfile = ZipFile(
                outfile_name,
                "w",
                dry_run=dry_run,
                ignore_missing=ignore_missing,
                deflate=deflate,
                ps=ps,
            )
        except FileNotFoundError as error:
            errmsg = "Could not write to Zip archive '{outfile}': {error}".format(
                outfile=outfile_name, error=error
            )
            print_err(errmsg)
            sys.exit(1)

        num_missing = 0
        with zipfile as outfile:
            for path, url in urls:

                if not verbose:
                    bar()

                filename = get_fs_path(path, url)

                if filename is None:
                    filename = recodeURL(url)

                try:
                    if outfile.write(filename) is not None:
                        num_missing += 1

                except FileNotFoundError as error:
                    errmsg = "Could not write {filename} to Zip ({error}).".format(
                        filename=filename, error=error
                    )
                    print_err(errmsg, "Aborting.", sep="\n", end=" ")
                    if not dry_run:
                        print_err("Zip file is incomplete.")
                    else:
                        print_err()
                    sys.exit(1)

            # Finally, include the save file itself.
            outfile.write(infile_name, os.path.join("Mods/Workshop", os.path.basename(infile_name)))

            # Check if there is a thumbnail for the mod
            thumb_filename = os.path.splitext(infile_name)[0] + ".png"
            if os.path.exists(thumb_filename):
                outfile.write(thumb_filename, os.path.join("Mods/Workshop", os.path.basename(thumb_filename)))

            # Store some metadata.
            outfile.put_metadata(comment=comment)
    
    if dry_run:
        print("Dry run for {file} completed.".format(file=infile_name))
    else:
        zipfile.close()

        # Check if we have any old zipfiles for this mod with filename used with missing files
        glob_path = glob.escape(f"{os.path.splitext(outfile_name)[0]}")
        old_files = glob.glob(f"{glob_path} (-*{os.path.splitext(outfile_name)[1]}")

        if len(old_files) > 0:
            for f_name in old_files:
                os.remove(f_name)

        # Modify backup filename to include number of missing files detected
        if num_missing > 0:
            new_name = f"{os.path.splitext(outfile_name)[0]} (-{num_missing}){os.path.splitext(outfile_name)[1]}"
            os.rename(outfile_name, new_name)
            outfile_name = new_name

        if verbose:
            print(
                "Backed-up contents for {file} in {outfile}.".format(
                    file=infile_name, outfile=outfile_name
                )
            )

def backup_files(args):

    outfile_name = args.outfile_name
    orig_path = os.getcwd()
    out_dir = orig_path

    if outfile_name:
        # We need to determine if outfile_name is a directory or filename
        # also determine if the path is absolute or relative to current directory
        if os.path.isdir(outfile_name):
            out_dir = outfile_name
            outfile_name = ''
        else:
            out_dir = os.path.dirname(outfile_name)
            outfile_name = os.path.basename(outfile_name)

        if not os.path.isabs(out_dir):
            out_dir = os.path.join(orig_path, out_dir)

    if args.backup_all:
        infile_names = []
        outfile_name = ''
        infile_dir = args.infile_name
        if not os.path.exists(infile_dir):
            infile_dir = os.path.join(args.gamedata_dir, os.path.join('Mods', infile_dir))
        if not os.path.exists(infile_dir):
            print_err(f"Cannot find directory {infile_dir}")
            sys.exit(1)
        else:
            infile_names += get_mods_in_directory(infile_dir, os.path.join(out_dir, 'backup_mtimes.pkl'))
    else:
        infile_names = [args.infile_name]

    for infile_name in infile_names:

        if not os.path.exists(infile_name):
            infile_name = os.path.join(os.path.join(args.gamedata_dir, 'Mods/Workshop'), infile_name)

        try:
            backup_json(
                infile_name,
                out_dir,
                outfile_name,
                comment=args.comment,
                dry_run=args.dry_run,
                gamedata_dir=args.gamedata_dir,
                ignore_missing=args.ignore_missing,
                deflate=args.deflate,
                verbose=args.verbose
            )

        except (FileNotFoundError, IllegalSavegameException, SystemExit):
            print_err("Aborting.")
            sys.exit(1)
        
        if not args.dry_run:
            save_modification_time(infile_name, os.path.join(out_dir, 'backup_mtimes.pkl'))