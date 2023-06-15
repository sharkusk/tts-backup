import io
import json
import os
import time
import zipfile
import pickle
from importlib.metadata import version

REVISION = version("tts-backup")


class ShadowProxy:
    """Proxy objects for arbitrary objects, with the ability to divert
    attribute access from one attribute to another.

    """

    def __init__(self, proxy_for):
        self.__target = proxy_for
        self.__diverted = {}

    def divert_access(self, source, target):
        self.__diverted[source] = target

    def __getattr__(self, name):
        if name in self.__diverted:
            name = self.__diverted[name]
        return getattr(self.__target, name)


class ZipFile(zipfile.ZipFile):
    """A ZipFile that supports dry-runs.

    It also keeps track of files already written, and only writes them
    once. ZipFile.filelist would have been useful for this, but on
    Windows, this doesn’t seem to reflect writes before syncing the
    file to disk.
    """

    def __init__(self, *args, dry_run=False, ignore_missing=False, deflate=False, ps=None, **kwargs):

        self.dry_run = dry_run
        self.stored_files = set()
        self.ignore_missing = ignore_missing
        self.missing_files = ''

        if ps is None:
            self.ps = PrintStatus()
        else:
            self.ps = ps

        if not self.dry_run:
            if deflate:
                compression = zipfile.ZIP_DEFLATED
            else:
                compression = zipfile.ZIP_STORED
            super().__init__(*args, compression=compression, **kwargs)

    def __exit__(self, *args, **kwargs):

        if self.missing_files != '':
            if self.dry_run:
                print("Missing files:")
                print(self.missing_files)
            else:
                super().writestr("missing.txt", self.missing_files)

        if not self.dry_run:
            super().__exit__(*args, **kwargs)

    def write(self, filename, *args, **kwargs):

        if filename in self.stored_files:
            return None

        self.stored_files.add(filename)

        # Logging.
        curdir = os.getcwd()
        absname = os.path.join(curdir, filename)

        def log_skipped():
            self.ps.print("{} (not found)".format(absname))
            self.missing_files += f"{filename}\n"

        def log_written():
            self.ps.print(absname)

        if not (os.path.isfile(filename) or self.ignore_missing):
            raise FileNotFoundError("No such file: {}".format(filename))

        if self.dry_run and os.path.isfile(filename):
            log_written()

        elif self.dry_run:
            log_skipped()

        else:
            try:
                super().write(filename, *args, **kwargs)
            except FileNotFoundError:
                assert self.ignore_missing
                log_skipped()
            else:
                log_written()
                filename = None

        # If filename is not none then there was a problem writing it, so notify
        # the caller than this file was not stored...
        return filename

    def put_metadata(self, comment=None):
        """Create a MANIFEST file and store it within the archive."""

        manifest = dict(
            script_revision=REVISION, export_date=round(time.time())
        )

        if comment:
            manifest["comment"] = comment

        manifest = json.dumps(manifest)
        self.comment = manifest.encode("utf-8")


def print_err(*args, **kwargs):
    # stderr could be reset at run-time, so we need to import it when
    # the function runs, not when this module is imported.
    from sys import stderr

    if "file" in kwargs:
        del kwargs["file"]
    print(*args, file=stderr, **kwargs)


def strip_mime_parms(mime_type):
    "Remove any MIME parameters from a content-type header value."
    idx = mime_type.find(";")
    has_parms = idx >= 0
    if has_parms:
        return mime_type[:idx]
    else:
        return mime_type


def make_safe_filename(filename):
    return "".join([c if c.isalpha() or c.isdigit() or c in ' ()[]-_{}.' else '-' for c in filename]).rstrip() 


def get_mods_in_directory(dir_path, mtime_filename):

    modified_times = {}
    try:
        with open(mtime_filename, 'rb') as f:
            modified_times = pickle.load(f)
    except FileNotFoundError:
        pass
    
    def get_mtime(name, modified_times):
        try:
            return modified_times[name]
        except:
            return 0.0

    infile_names = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
                    if os.path.splitext(f)[1] == '.json' and
                    os.path.getmtime(os.path.join(dir_path, f)) > get_mtime(f, modified_times) and
                    os.path.basename(f) != 'WorkshopFileInfos.json']

    return infile_names


def save_modification_time(infile_name, mtime_filename):
    modified_times = {}
    try:
        with open(mtime_filename, 'rb') as f:
            modified_times = pickle.load(f)
    except FileNotFoundError:
        pass

    modified_times[os.path.basename(infile_name)] = os.path.getmtime(infile_name)

    with open(mtime_filename, 'wb') as f:
        pickle.dump(modified_times, f)


class PrintStatus():

    def __init__(self, bar=None, verbose=True):
        self.buffered_text = ""
        self.bar = bar
        self.verbose = verbose

    def print(self, *args, **kwargs):
        if not self.verbose:
            return
        if self.bar:
            if 'end' in kwargs.keys() and kwargs['end'] == "":
                output = io.StringIO()
                print(*args, file=output, **kwargs)
                self.buffered_text += output.getvalue()
                output.close()
            else:
                output = io.StringIO()
                print(*args, file=output, **kwargs)
                contents = output.getvalue()
                output.close()

                self.bar.text(self.buffered_text + contents)
                self.buffered_text = ""
        else:
            print(*args, **kwargs)
