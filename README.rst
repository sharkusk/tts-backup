TTS-Backup
==========

TTS-Backup backs up Tabletop simulator save games and mods to a Zip
file, bundling locally cached images and models within a single
archive.

This only handles saves and mods in JSON format.

.. image:: https://user-images.githubusercontent.com/4368882/245197642-5bbfbafe-ceae-460d-956b-e6cc86d1772e.gif


Requirements & Installation
---------------------------

A Python 3.5 (or newer) interpreter is required. For Windows users, the
`ActivePython <http://www.activestate.com/activepython/downloads>`__
distribution is recommended.

.. |ss| raw:: html

   <strike>

.. |se| raw:: html

   </strike>

|ss|
Alternatively, a binary release for the Windows platform is available
`here
<https://github.com/eigengrau/tts-backup/releases/tag/win32-frozen>`__.
|se|

Optionally, to use the source distribution, download the current
`release <https://github.com/eigengrau/tts-backup/releases>`__, and
either use ``pip`` or ``easy_install`` on the archive file, or extract
the contents and run ``python setup.py install``.

If you wish to install the code in place (i.e. any updates to the repository
will automaticaly be used) you can install using ``pip install -e .`` from
the directory containing the tts-backup code.


Usage
-----

All content referenced within the mod or save must have been locally cached
from within TTS before a backup can be made. Note that when game items are
contained within bags, TTS will only locally cache the respective assets
once they are removed from the bag. To avoid this problem, use the
``tts-prefetch`` tool to cache assets before running a backup operation.


Tabletop Simulator Data Directory
---------------------------------

By default, TTS-Backup will assume that cached data is located in
``~/Documents/My Games/Tabletop Simulator``.  This can be overridden 
using the ``--gamedata`` parameter.  To override the default directory
without having to use the gamedata parameter on every run, a text file with
the name ``mod_location.txt`` can be placed in the default directory
containing a single line with the location of the ``Tabletop Simulator_Data``
directory.

Example ``mod_location.txt`` file (stored in ``~/Documents/My Games/Tabletop Simulator``):
::
  D:\SteamLibrary\steamapps\common\Tabletop Simulator\Tabletop Simulator_Data


Tracking Mod's Modified Time
-----------------------------

When a backup is completed, the mod file's modification time is stored in the
``backup_mtimes.pkl`` file contained in the backup directory (or current directory
if no backup directory was specified).  This is ignored if an individual
mod file is selected for backup at the command line.  However, when backing up using
the ``--backup-all`` feature, only mods that are newer than their last backup will
be processed.


Missing File Features
---------------------

If any files are found to be missing during the backup operation a text
file containing a list of the missing files will be created in the root
of the zip file.

The number of missing files will also be appended to the end of the backup
file name (as a negative number in parens).
e.g. ``Clank- Legacy- Acquisitions Incorporated [2100953124] (-80).zip``


Examples
--------

``> tts-backup 2495129405.json``

This will backup Mods/Workshop/2495129405.json

``> tts-backup -a Workshop``

This will backup all json files found in the Mods/Workshop directory
if their modification time is newer than what is found in the
Mods/Workshop/backup_mtimes.pkl file.

Usage flags and arguments are as follows:

::

  positional arguments:
    FILENAME              The save file or mod in JSON format.

  options:
    -h, --help            show this help message and exit
    --backup_all, -a      Backup all mods in the directory specified by FILENAME.
    --gamedata PATH       The path to the TTS game data dircetory.
    --outname FILENAME, -o FILENAME
                          The name (or directory for multiple backups) for the output archive.
    --dry-run, -n         Only print which files would be backed up.
    --ignore-missing, -i  Do not abort the backup when files are missing.
    --comment COMMENT, -c COMMENT
                          A comment to be stored in the resulting Zip.
    --deflate, -z         Enable zlib compression in the zip file


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


Tabletop Simulator Data Directory
---------------------------------

Cf. above.


Tracking Mod's Modified Time
-----------------------------

When a backup is completed, the mod file's modification time is stored in the
``prefetch_mtimes.pkl`` file in the same directory as the mod.json file.  This 
is ignored if individual mod files are selected for prefetch at the command line.
However, when prefetching using the ``--prefetch-all`` feature, only mods that
are newer than their last prefetch will be processed.

Missing File Features
---------------------

If any files are found to be missing during the prefetch operation a text
file containing a list of the missing files will be created in the directory
containing the mod.json file.


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
                         

Suggested Workflow
==================
1. Perform prefetch of all subscribed mods:  ``> tts-prefetch -a Workshop``
2. Create a backup directory, and cd to that directory.  Perform backup of all subscribed mods from that directory: ``> tts-backup -a Workshop``
3. After running TTS, when notification that one or more mods have been updated, repeat steps 1 and 2.  The Prefetch and backup operations will only be performed on the updated mods.
