#!/usr/bin/python3

import argparse
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import signal

from libtts import (urls_from_save,
                    is_obj,
                    is_image,
                    get_fs_path,
                    GAMEDATA_DEFAULT)


parser = argparse.ArgumentParser(
    description='Download assets referenced in TTS .json files.'
)

parser.add_argument(
    'infile_names',
    metavar="FILENAME",
    nargs='+',
    help='The save file or mod in JSON format.'
)

parser.add_argument(
    '--gamedata',
    dest="gamedata_dir",
    metavar="PATH",
    default=GAMEDATA_DEFAULT,
    help='The path to the TTS game data directory.'
)

parser.add_argument(
    '--dry-run', '-n',
    dest="dry_run",
    default=False,
    action='store_true',
    help='Only print which files would be downloaded.'
)

parser.add_argument(
    '--refetch', '-r',
    dest="refetch",
    default=False,
    action='store_true',
    help='Rewrite objects that already exist in the cache.'
)

parser.add_argument(
    '--relax', '-x',
    dest="ignore_content_type",
    default=False,
    action='store_true',
    help="Do not abort when encountering an unexpected MIME type."
)

parser.add_argument(
    '--timeout', '-t',
    dest="timeout",
    default=5,
    type=int,
    help="Connection timeout in s."
)


def sigint_handler(signum, frame):
    sys.exit(1)


def prefetch_file(filename,
                  refetch=False,
                  ignore_content_type=False,
                  dry_run=False,
                  gamedata_dir=GAMEDATA_DEFAULT,
                  timeout=5,
                  semaphore=None):

    print("Prefetching assets for %s." % filename)

    try:
        urls = urls_from_save(filename)
    except FileNotFoundError as error:
        print("%s: %s" % (error.strerror, error.filename))
        raise

    done = set()
    for path, url in urls:

        if semaphore and semaphore.acquire(blocking=False):
            print("Aborted.")
            return

        # Some mods contain malformed URLs missing a prefix. I’m not
        # sure how TTS deals with these. Let’s assume http for now.
        if not urllib.parse.urlparse(url).scheme:
            print("Warning: URL %s does not specify a URL scheme. "
                  "Assuming http." % url, file=sys.stderr)
            fetch_url = "http://" + url
        else:
            fetch_url = url

        # A mod might refer to the same URL multiple times.
        if url in done:
            continue

        # To prevent downloading unexpected content, we check the MIME
        # type in the response.
        if is_obj(path, url):
            content_expected = lambda mime: any(map(mime.startswith,
                                                    ("text/plain",
                                                     "application/json")))
        elif is_image(path, url):
            content_expected = lambda mime: mime in ("image/jpeg",
                                                     "image/png")
        else:
            raise ValueError("Do not know how to retrieve URL %s at %s." %
                             (url, path))

        outfile_name = os.path.join(gamedata_dir, get_fs_path(path, url))

        # Check if the object is already cached.
        if os.path.isfile(outfile_name) and not refetch:
            done.add(url)
            continue

        print("%s " % url, end="")

        if dry_run:
            print("dry run")
            done.add(url)
            continue

        try:
            response = urllib.request.urlopen(fetch_url, timeout=timeout)
        except urllib.error.HTTPError as error:
            print("Error %s (%s)" % (error.code, error.reason),
                  file=sys.stderr)
            continue
        except urllib.error.URLError as error:
            print("Error (%s)" % error.reason, file=sys.stderr)
            continue

        # Only for informative purposes.
        length = response.getheader('Content-Length', 0)
        length_kb = "???"
        if length:
            try:
                length_kb = "%i" % (int(length) / 1000)
            except ValueError:
                pass
        print("(%s kb): " % length_kb, end="", flush=True)

        content_type = response.getheader('Content-Type').strip()
        is_expected = content_expected(content_type)
        if not (is_expected or ignore_content_type):
            print("Error: Content type %s does not match expected type. "
                  "Aborting. Use --relax to ignore." % content_type,
                  file=sys.stderr)
            sys.exit(1)

        try:
            with open(outfile_name, "wb") as outfile:
                outfile.write(response.read())
            print("ok")
        except FileNotFoundError as error:
            print("%s: %s" % (error.strerror, error.filename),
                  file=sys.stderr)
            raise
        except:
            # Don’t leave files with partial content lying around.
            try:
                os.remove(outfile_name)
            except FileNotFoundError:
                pass
            raise

        if not is_expected:
            print("Warning: Content type %s did not match expected type." %
                  content_type, file=sys.stderr)

        done.add(url)

    if dry_run:
        print("Dry-run for %s completed." % filename)
    else:
        print("Prefetching %s completed." % filename)


def main(args, semaphore=None):

    for infile_name in args.infile_names:

        try:
            prefetch_file(infile_name,
                          dry_run=args.dry_run,
                          refetch=args.refetch,
                          ignore_content_type=args.ignore_content_type,
                          gamedata_dir=args.gamedata_dir,
                          timeout=args.timeout,
                          semaphore=semaphore)

        except FileNotFoundError:
            print("Aborting.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":

    signal.signal(signal.SIGINT, sigint_handler)
    args = parser.parse_args()
    main(args)
