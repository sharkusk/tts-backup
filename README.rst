TTS-Backup
==========

TTS-Backup backs up Tabletop simulator save games and mods to a Zip
file, bundling locally cached images and models within a single
archive.

This only handles saves and mods in JSON format.


Requirements & Installation
---------------------------

A Python 3.5 (or newer) interpreter is required. For Windows users, the
`ActivePython <http://www.activestate.com/activepython/downloads>`__
distribution is recommended.

Alternatively, a binary release for the Windows platform is available
`here
<https://github.com/eigengrau/tts-backup/releases/tag/win32-frozen>`__.

Optionally, to use the source distribution, download the current
`release <https://github.com/eigengrau/tts-backup/releases>`__, and
either use ``pip`` or ``easy_install`` on the archive file, or extract
the contents and run ``python setup.py install``.


Usage
-----

All content referenced within the mod or save must have been locally
cached from within TTS before a backup can be made. Note that when
game items are contained within bags, TTS will only locally cache the
respective assets once they are removed from the bag.

By default, TTS-Backup will assume that cached data is located in
``~/Documents/My Games/Tabletop Simulator``.

TTS-Backup is a console application. For stern opponents of the CLI, a
minimal GUI is provided.

Usage flags and arguments are as follows:

::

    usage: tts-backup [-h] [--gamedata PATH] [--outname FILENAME] [--dry-run]
                      [--ignore-missing] [--comment COMMENT]
                      FILENAME

    Back-up locally cached content from a TTS .json file.

    positional arguments:
      FILENAME              The save file or mod in JSON format.

    optional arguments:
      -h, --help            show this help message and exit
      --gamedata PATH       The path to the TTS game data directory.
      --outname FILENAME, -o FILENAME
                            The name for the output archive.
      --dry-run, -n         Only print which files would be backed up.
      --ignore-missing, -i  Don’t abort the backup when files are missing.
      --comment COMMENT, -c COMMENT
                            A comment to be stored in the resulting Zip.


TTS-Prefetch
============

TTS-Prefetch downloads assets specified within a TTS JSON save file
(including links found in LuaScript sections) and stores them within
the TTS cache. This is handy if you want to ensure that all mod assets
are present, e. g., when several mods have been updated, or when a mod
uses bags, which normally require that all pieces are unpacked manually
before they are fetched and stored inside the TTS cache.


Requirements & Installation
---------------------------

Cf. above.


Usage
-----

By default, TTS-Prefetch will assume that cached data is located in
``~/Documents/My Games/Tabletop Simulator``.  However, if cached data
is stored elsewhere, a text file with the name ``mod_location.txt`` can
be placed in this directory containing a single line with the location
of the directory
(e.g. ``D:\SteamLibrary\steamapps\common\Tabletop Simulator\Tabletop Simulator_Data``)

When a mod if prefetched, the mod file's modification time is stored in the
``prefetch_mtimes.pkl`` file contained in the same directory as the json file.


Examples
--------

``> tts-prefetch 2495129405.json 2491200259.json``

This will prefetch  ``Mods/Workshop/2495129405.json`` and ``Mods/Workshop/2491200259.json``

``> tts-prefetch -a Workshop``

This will prefetch all json files found in the Mods/Workshop directory
if their modification time is newer than what is found in the
``Mods/Workshop/prefetch_mtimes.pkl`` file.

Usage flags and arguments are as follows:

::

  positional arguments:
    FILENAME              The save file or mod in JSON format.

  options:
    -h, --help            show this help message and exit
    --prefetch_all, -a    Prefetch all in the directory specified by FILENAME.
    --gamedata PATH       The path to the TTS game data directory.
    --dry-run, -n         Only print which files would be downloaded.
    --refetch, -r         Rewrite objects that already exist in the cache.
    --relax, -x           Do not abort when encountering an unexpected MIME type.
    --timeout TIMEOUT, -t TIMEOUT
                          Connection timeout in s.
    --user-agent USER_AGENT, -u USER_AGENT
                          HTTP user-agent string.