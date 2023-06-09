from contextlib import suppress
from tts_tools.libtts import GAMEDATA_DEFAULT
from tts_tools.libtts import get_fs_path
from tts_tools.libtts import get_fs_path_from_extension
from tts_tools.libtts import get_save_name
from tts_tools.libtts import IllegalSavegameException
from tts_tools.libtts import is_assetbundle
from tts_tools.libtts import is_audiolibrary
from tts_tools.libtts import is_image
from tts_tools.libtts import is_obj
from tts_tools.libtts import is_pdf
from tts_tools.libtts import is_from_script
from tts_tools.libtts import urls_from_save
from tts_tools.util import print_err

import http.client
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request


def prefetch_file(
    filename,
    refetch=False,
    ignore_content_type=False,
    dry_run=False,
    gamedata_dir=GAMEDATA_DEFAULT,
    timeout=10,
    semaphore=None,
    user_agent="TTS prefetch",
):
    if not os.path.exists(filename):
        filename = os.path.join(os.path.join(gamedata_dir, 'Mods/Workshop'), filename)

    try:
        save_name = get_save_name(filename)
    except Exception:
        save_name = "???"

    cur_dir = os.getcwd()
    missing_filename = os.path.join(cur_dir, save_name) + ".txt"

    # get_fs_path is relative, so need to change to the gamedir directory
    # so existing file extensions can be properly detected
    os.chdir(gamedata_dir)

    print(
        "Prefetching assets for {file} ({save_name}).".format(
            file=filename, save_name=save_name
        )
    )

    try:
        urls = urls_from_save(filename)
    except (FileNotFoundError, IllegalSavegameException) as error:
        print_err(
            "Error retrieving URLs from {filename}: {error}".format(
                error=error, filename=filename
            )
        )
        raise

    missing = []
    done = set()
    for path, url in urls:

        if semaphore and semaphore.acquire(blocking=False):
            print("Aborted.")
            return

        # A mod might refer to the same URL multiple times.
        if url in done:
            continue

        # Only attempt to get a URL one time, even if there is an error
        done.add(url)

        # To prevent downloading unexpected content, we check the MIME
        # type in the response.
        if is_obj(path, url):

            def content_expected(mime):
                return any(
                    map(
                        mime.startswith,
                        (
                            "text/plain",
                            "application/binary",
                            "application/octet-stream",
                            "application/json",
                            "application/x-tgif",
                        ),
                    )
                )

        elif is_assetbundle(path, url):

            def content_expected(mime):
                return any(
                    map(
                        mime.startswith,
                        ("application/binary", "application/octet-stream"),
                    )
                )

        elif is_image(path, url):

            def content_expected(mime):
                return mime in (
                    "image/jpeg",
                    "image/jpg",
                    "image/png",
                    "application/octet-stream",
                    "application/binary",
                    "video/mp4",
                )

        elif is_audiolibrary(path, url):

            def content_expected(mime):
                return mime in (
                    "application/octet-stream",
                    "application/binary",
                ) or mime.startswith("audio/")

        elif is_pdf(path, url):

            def content_expected(mime):
                return mime in (
                    "application/pdf",
                    "application/binary",
                    "application/octet-stream",
                )
        
        elif is_from_script(path, url):
            def content_expected(mime):
                return mime in (
                    "application/pdf",
                    "application/binary",
                    "application/octet-stream",
                    "application/json",
                    "application/x-tgif",
                    "image/jpeg",
                    "image/jpg",
                    "image/png",
                    "video/mp4",
                )

        else:
            errstr = "Do not know how to retrieve URL {url} at {path}.".format(
                url=url, path=path
            )
            raise ValueError(errstr)

        outfile_name = get_fs_path(path, url)
        if outfile_name is not None:
            # Check if the object is already cached.
            if os.path.isfile(outfile_name) and not refetch:
                continue

        # Some mods contain malformed URLs missing a prefix. I’m not
        # sure how TTS deals with these. Let’s assume http for now.
        if not urllib.parse.urlparse(url).scheme:
            print_err(
                "Warning: URL {url} does not specify a URL scheme. "
                "Assuming http.".format(url=url)
            )
            fetch_url = "http://" + url
        else:
            fetch_url = url

        print("{} ".format(url), end="", flush=True)

        if dry_run:
            print("dry run")
            continue

        headers = {"User-Agent": user_agent}
        request = urllib.request.Request(url=fetch_url, headers=headers)

        try:
            response = urllib.request.urlopen(request, timeout=timeout)

        except urllib.error.HTTPError as error:
            print_err(
                "Error {code} ({reason})".format(
                    code=error.code, reason=error.reason
                )
            )
            missing.append((url, f"HTTPError {error.code} ({error.reason})"))
            continue

        except urllib.error.URLError as error:
            print_err("Error ({reason})".format(reason=error.reason))
            missing.append((url, f"URLError ({error.reason})"))
            continue

        except socket.timeout as error:
            print_err("Error ({reason})".format(reason=error))
            missing.append((url, f"Timeout ({error})"))
            continue

        except http.client.HTTPException as error:
            print_err("HTTP error ({reason})".format(reason=error))
            missing.append((url, f"HTTPException ({error})"))
            continue
    
        if os.path.basename(response.url) == 'removed.png':
            # Imgur sends bogus png when files are missing, ignore them
            print_err("Removed")
            missing.append((url, f"Removed"))
            continue

        # Only for informative purposes.
        length = response.getheader("Content-Length", 0)
        length_kb = "???"
        if length:
            with suppress(ValueError):
                length_kb = int(length) / 1000
        size_msg = "({length} kb): ".format(length=length_kb)

        content_type = response.getheader("Content-Type", "").strip()
        is_expected = not content_type or content_expected(content_type)
        if not (is_expected or ignore_content_type):
            # Google drive sends html error page when file is removed/missing
            print_err(
                "Error: Wrong Content type {type}.".format(type=content_type)
            )
            missing.append((url, f"Wrong context type ({content_type})"))
            continue

        filename_ext = ''
        ext = ''

        # Format of content disposition looks like this:
        # 'attachment; filename="03_Die nostrische Hochzeit (Instrumental).mp3"; filename*=UTF-8\'\'03_Die%20nostrische%20Hochzeit%20%28Instrumental%29.mp3'
        content_disposition = response.getheader("Content-Disposition", "").strip()
        offset = content_disposition.find('filename="')
        if offset > 0:
            name = content_disposition[offset:].split('"')[1]
            _, filename_ext = os.path.splitext(name)
        else:
            # Use the url to extract the extension, ignoring any trailing ? url parameters
            offset = url.rfind("?")
            if offset > 0:
                _, filename_ext = os.path.splitext(url[0:url.rfind("?")])
            else:
                _, filename_ext = os.path.splitext(url)

        if outfile_name is None:
            ext = filename_ext
            outfile_name = get_fs_path_from_extension(url, ext)
        else:
            # Check if we know the extension of our filename.  If not, use
            # the data in the response to determine the appropriate extension.
            _, ext = os.path.splitext(outfile_name)
            if ext == '':
                if content_type in ['image/png']:
                    ext = '.png'
                elif content_type in ['image/jpg', 'image/jpeg']:
                    ext = '.jpg'
                else:
                    ext = filename_ext
                if ext == '':
                    print_err(
                        "Error: Cannot find extension for {name}. Aborting".format(name=outfile_name)
                    )
                    sys.exit(1)

                outfile_name = outfile_name + ext

        print(f"\n ...{outfile_name}: {size_msg}", end="", flush=True)

        try:
            with open(outfile_name, "wb") as outfile:
                outfile.write(response.read())

        except FileNotFoundError as error:
            print_err("Error writing object to disk: {}".format(error))
            missing.append((url, f"Error writing to disk ({error})"))
            raise

        # Don’t leave files with partial content lying around.
        except Exception:
            with suppress(FileNotFoundError):
                os.remove(outfile_name)
            raise

        else:
            print("ok")

        if not is_expected:
            errmsg = (
                "Warning: Content type {} did not match "
                "expected type.".format(content_type)
            )
            print_err(errmsg)
    
    if len(missing) > 0:
        print_err(f"{len(missing)} URLs missing!")
        print_err(f"Saving missing file list to {missing_filename}.")

        with open(missing_filename, 'w') as f:
            for url, error in missing:
                f.write(f"{url}: {error}\n")

    if dry_run:
        completion_msg = "Dry-run for {} completed."
    else:
        completion_msg = "Prefetching {} completed."
    print(completion_msg.format(filename))


def prefetch_files(args, semaphore=None):

    for infile_name in args.infile_names:

        try:
            prefetch_file(
                infile_name,
                dry_run=args.dry_run,
                refetch=args.refetch,
                ignore_content_type=args.ignore_content_type,
                gamedata_dir=args.gamedata_dir,
                timeout=args.timeout,
                semaphore=semaphore,
                user_agent=args.user_agent,
            )

        except (FileNotFoundError, IllegalSavegameException, SystemExit):
            print_err("Aborting.")
            sys.exit(1)
