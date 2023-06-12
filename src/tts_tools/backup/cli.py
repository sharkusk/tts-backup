from tts_tools.backup import backup_files
from tts_tools.libtts import GAMEDATA_DEFAULT

import argparse
import signal
import sys
from importlib.metadata import version

description = '''
TTS-Backup
============
TTS-Backup backs up Tabletop simulator save games and mods to a Zip file,
bundling locally cached images and models within a single archive.

This only handles saves and mods in JSON format.

Usage
-----

All content referenced within the mod or save must have been locally cached
from within TTS before a backup can be made. Note that when game items are
contained within bags, TTS will only locally cache the respective assets
once they are removed from the bag.

By default, TTS-Backup will assume that cached data is located in
``~/Documents/My Games/Tabletop Simulator``.  However, if cached data
is stored elsewhere, a text file with the name 'mod_location.txt' can
be placed in this directory containing a single line with the location
of the directory
(e.g. D:\SteamLibrary\steamapps\common\Tabletop Simulator\Tabletop Simulator_Data)

When a backup is completed, the mod file's modification time is stored in the
'backup_mtimes.pkl' file contained in the backup directory (or current directory
if no backup directory was specified).

If any files are found to be missing during the backup operation a text
file containing a list of the missing files will be created in the root
of the zip file.

Examples
--------

> tts-backup 2495129405.json
This will backup Mods/Workshop/2495129405.json

> tts-backup -a Workshop
This will backup all json files found in the Mods/Workshop directory
if their modification time is newer than what is found in the
Mods/Workshop/backup_mtimes.pkl file.

Usage flags and arguments are as follows:
'''

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=description
)

parser.add_argument(
    "--version",
    action='version',
    version=version("tts-backup")
)

parser.add_argument(
    "infile_name",
    metavar="FILENAME",
    help="The save file or mod in JSON format.",
)

parser.add_argument(
    "--backup_all",
    "-a",
    dest="backup_all",
    default=False,
    action="store_true",
    help="Backup all mods in the directory specified by FILENAME.",
)

parser.add_argument(
    "--gamedata",
    dest="gamedata_dir",
    metavar="PATH",
    default=GAMEDATA_DEFAULT,
    help="The path to the TTS game data dircetory.",
)

parser.add_argument(
    "--outname",
    "-o",
    dest="outfile_name",
    metavar="FILENAME",
    default=None,
    help="The name (or directory for multiple backups) for the output archive.",
)

parser.add_argument(
    "--dry-run",
    "-n",
    dest="dry_run",
    default=False,
    action="store_true",
    help="Only print which files would be backed up.",
)

parser.add_argument(
    "--ignore-missing",
    "-i",
    dest="ignore_missing",
    default=False,
    action="store_true",
    help="Do not abort the backup when files are missing.",
)

parser.add_argument(
    "--comment",
    "-c",
    dest="comment",
    default="",
    help="A comment to be stored in the resulting Zip.",
)

parser.add_argument(
    "--deflate",
    "-z",
    dest="deflate",
    default=False,
    action="store_true",
    help="Enable zlib compression in the zip file",
)

parser.add_argument(
    "--verbose",
    "-v",
    dest="verbose",
    default=False,
    action="store_true",
    help="Verbose print output, disables progress bar.",
)

def sigint_handler(signum, frame):
    sys.exit(1)

def console_entry():

    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)
    args = parser.parse_args()
    backup_files(args)
