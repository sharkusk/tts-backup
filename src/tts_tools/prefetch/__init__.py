from contextlib import suppress
from tts_tools.libtts import GAMEDATA_DEFAULT
from tts_tools.libtts import get_fs_path
from tts_tools.libtts import get_fs_path_from_extension
from tts_tools.libtts import fix_ext_case
from tts_tools.libtts import get_save_name
from tts_tools.libtts import IllegalSavegameException
from tts_tools.libtts import is_assetbundle
from tts_tools.libtts import is_audiolibrary
from tts_tools.libtts import is_image
from tts_tools.libtts import is_obj
from tts_tools.libtts import is_pdf
from tts_tools.libtts import is_from_script
from tts_tools.libtts import is_custom_ui_asset
from tts_tools.libtts import urls_from_save
from tts_tools.util import print_err
from tts_tools.util import make_safe_filename

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
    try:
        save_name = get_save_name(filename)
    except Exception:
        save_name = "???"

    cur_dir = os.getcwd()

    # get_fs_path is relative, so need to change to the gamedir directory
    # so existing file extensions can be properly detected
    os.chdir(gamedata_dir)

    print(
        "\nPrefetching assets for {file} [{save_name}].".format(
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

        # Some mods contain malformed URLs missing a prefix. I’m not
        # sure how TTS deals with these. Let’s assume http for now.
        if not urllib.parse.urlparse(url).scheme:
            fetch_url = "http://" + url
        else:
            fetch_url = url

        try:
            if urllib.parse.urlparse(fetch_url).hostname.find('localhost') >= 0:
                continue
        except:
            # URL was so badly formatted that there is no hostname.
            missing.append((url, f"Invalid hostname"))
            continue

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
        
        elif is_from_script(path, url) or is_custom_ui_asset(path, url):

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

        print("{} ".format(url), end="", flush=True)

        if dry_run:
            print("dry run")
            continue

        headers = {"User-Agent": user_agent}

        request_error = False

        while(True):
            request = urllib.request.Request(url=fetch_url, headers=headers)

            try:
                response = urllib.request.urlopen(request, timeout=timeout)

            except socket.timeout as error:
                print_err("Error ({reason})".format(reason=error))
                continue

            except urllib.error.HTTPError as error:
                print_err(
                    "Error {code} ({reason})".format(
                        code=error.code, reason=error.reason
                    )
                )
                missing.append((url, f"HTTPError {error.code} ({error.reason})"))
                request_error = True

            except urllib.error.URLError as error:
                print_err("Error ({reason})".format(reason=error.reason))
                missing.append((url, f"URLError ({error.reason})"))
                request_error = True

            except http.client.HTTPException as error:
                print_err("HTTP error ({reason})".format(reason=error))
                missing.append((url, f"HTTPException ({error})"))
                request_error = True
        
            try:
                if os.path.basename(response.url) == 'removed.png':
                    # Imgur sends bogus png when files are missing, ignore them
                    print_err("Removed")
                    missing.append((url, f"Removed"))
                    request_error = True
            except UnboundLocalError:
                pass

            # We only continue to retry due to timeouts, otherwise break out of while loop
            break

        if request_error:
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
        
        # TTS saves some file extensions as upper case
        filename_ext = fix_ext_case(filename_ext)

        if outfile_name is None:
            ext = filename_ext
            outfile_name = get_fs_path_from_extension(url, ext)

            if outfile_name is None:
                print_err(
                    "Unknown file type {type}.".format(type=ext)
                )
                missing.append((url, f"Unknown file type ({ext})"))
                continue
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
        
        mod_dir = os.path.split(os.path.split(outfile_name)[0])[1]
        print(f"{ext} -> {mod_dir}: {size_msg}", end="", flush=True)

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
        workshop_id = os.path.splitext(os.path.basename(filename))[0]
        dest = os.path.dirname(filename)
        safe_save_name = make_safe_filename(save_name)
        missing_filename = f"{workshop_id} [{safe_save_name}] missing.txt"
        missing_path = os.path.join(dest, missing_filename)

        print_err(f"{len(missing)} URLs missing!")
        print_err(f"Saving missing file list to {missing_path}.")

        with open(missing_path, 'w') as f:
            for url, error in missing:
                f.write(f"{url}: {error}\n")

    if dry_run:
        completion_msg = "Dry-run for {} completed."
    else:
        completion_msg = "Prefetching {} completed."
    print(completion_msg.format(filename))

import pickle

def prefetch_files(args, semaphore=None):

    if args.prefetch_all:

        # TODO: Move directory scanning to utils so it can be reused by backup script

        for infile_dir in args.infile_names:
            if not os.path.exists(infile_dir):
                infile_dir = os.path.join(GAMEDATA_DEFAULT, os.path.join('Mods', infile_dir))
            if not os.path.exists(infile_dir):
                print_err(f"Cannot find directory {infile_dir}")
                continue

            modified_times = {}
            try:
                with open(os.path.join(infile_dir, 'prefetch_mtimes.pkl'), 'rb') as f:
                    modified_times = pickle.load(f)
            except FileNotFoundError:
                pass
            
            def get_mtime(name, modified_times):
                try:
                    return modified_times[name]
                except:
                    return 0.0

            infile_names = [os.path.join(infile_dir, f) for f in os.listdir(infile_dir)
                            if os.path.splitext(f)[1] == '.json' and
                            os.path.getmtime(os.path.join(infile_dir, f)) > get_mtime(f, modified_times) and
                            os.path.basename(f) != 'WorkshopFileInfos.json']

    else:
        infile_names = args.infile_names

    for infile_name in infile_names:

        if not os.path.exists(infile_name):
            infile_name = os.path.join(os.path.join(GAMEDATA_DEFAULT, 'Mods/Workshop'), infile_name)

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

        modified_times = {}
        try:
            with open(os.path.join(os.path.dirname(infile_name), 'prefetch_mtimes.pkl'), 'rb') as f:
                modified_times = pickle.load(f)
        except FileNotFoundError:
            pass

        modified_times[os.path.basename(infile_name)] = os.path.getmtime(infile_name)

        with open(os.path.join(os.path.dirname(infile_name), 'prefetch_mtimes.pkl'), 'wb') as f:
            pickle.dump(modified_times, f)
