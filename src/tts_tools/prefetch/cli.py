from tts_tools.libtts import GAMEDATA_DEFAULT
from tts_tools.prefetch import prefetch_files

import argparse
import signal
import sys

description = '''
TTS-Prefetch
============

TTS-Prefetch downloads assets specified within a TTS JSON save file
(including links found in LuaScript sections) and stores them within
the TTS cache. This is handy if you want to ensure that all mod assets
are present, e. g., when several mods have been updated, or when a mod
uses bags, which normally require that all pieces are unpacked manually
before they are fetched and stored inside the TTS cache.

Usage
-----

By default, TTS-Prefetch will assume that cached data is located in
``~/Documents/My Games/Tabletop Simulator``.  However, if cached data
is stored elsewhere, a text file with the name 'mod_location.txt' can
be placed in this directory containing a single line with the location
of the directory
(e.g. D:\SteamLibrary\steamapps\common\Tabletop Simulator\Tabletop Simulator_Data)

When a mod if prefetched, the mod file's modification time is stored in the
'prefetch_mtimes.pkl' file contained in the same directory as the json file.

If any files are found to be missing during the prefetch operation a text
file containing a list of the missing files will be created in the directory
containing the mod's json file.

Examples
--------

> tts-prefetch 2495129405.json 2491200259.json
This will prefetch Mods/Workshop/2495129405.json and Mods/Workshop/2491200259.json

> tts-prefetch -a Workshop
This will prefetch all json files found in the Mods/Workshop directory
if their modification time is newer than what is found in the
Mods/Workshop/prefetch_mtimes.pkl file.

Usage flags and arguments are as follows:
'''

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=description
)

parser.add_argument(
    "infile_names",
    metavar="FILENAME",
    nargs="+",
    help="The save file or mod in JSON format.",
)

parser.add_argument(
    "--prefetch_all",
    "-a",
    dest="prefetch_all",
    default=False,
    action="store_true",
    help="Prefetch all mods in the directory specified by FILENAME.",
)

parser.add_argument(
    "--gamedata",
    dest="gamedata_dir",
    metavar="PATH",
    default=GAMEDATA_DEFAULT,
    help="The path to the TTS game data directory.",
)

parser.add_argument(
    "--dry-run",
    "-n",
    dest="dry_run",
    default=False,
    action="store_true",
    help="Only print which files would be downloaded.",
)

parser.add_argument(
    "--refetch",
    "-r",
    dest="refetch",
    default=False,
    action="store_true",
    help="Rewrite objects that already exist in the cache.",
)

parser.add_argument(
    "--relax",
    "-x",
    dest="ignore_content_type",
    default=False,
    action="store_true",
    help="Do not abort when encountering an unexpected MIME type.",
)

parser.add_argument(
    "--timeout",
    "-t",
    dest="timeout",
    default=5,
    type=int,
    help="Connection timeout in s.",
)

parser.add_argument(
    "--user-agent",
    "-u",
    dest="user_agent",
    default="tts-backup",
    help="HTTP user-agent string.",
)


def sigint_handler(signum, frame):
    sys.exit(1)


def console_entry():

    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)
    args = parser.parse_args()
    prefetch_files(args)
