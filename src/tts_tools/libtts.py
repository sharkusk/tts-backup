import json
import os
import platform
import re

IMGPATH = os.path.join("Mods", "Images")
OBJPATH = os.path.join("Mods", "Models")
BUNDLEPATH = os.path.join("Mods", "Assetbundles")
AUDIOPATH = os.path.join("Mods", "Audio")
PDFPATH = os.path.join("Mods", "PDF")
TXTPATH = os.path.join("Mods", "Text")

AUDIO_EXTS = ['.mp3', '.wav', '.ogv', '.ogg']
IMG_EXTS = ['.png', '.jpg', '.mp4', '.m4v', '.webm', '.mov', '.unity3d']
OBJ_EXTS = ['.obj']
BUNDLE_EXTS = ['.unity3d']
PDF_EXTS = ['.pdf']
TXT_EXTS = ['.txt']

# TTS uses UPPER_CASE extensions for these files
UPPER_EXTS = AUDIO_EXTS + PDF_EXTS + TXT_EXTS

ALL_VALID_EXTS = AUDIO_EXTS + IMG_EXTS + OBJ_EXTS + BUNDLE_EXTS + PDF_EXTS + TXT_EXTS

# Order used to search to appropriate paths based on extension
# IMG comes last (or at least after BUNDLE) as we prefer to store
# unity3d files as bundles (but there are cases where unity3d files
# are used as images -- specifically noticed for decks)
MOD_PATHS = [
    (AUDIO_EXTS, AUDIOPATH),
    (OBJ_EXTS, OBJPATH),
    (BUNDLE_EXTS, BUNDLEPATH),
    (PDF_EXTS, PDFPATH),
    (TXT_EXTS, TXTPATH),
    (IMG_EXTS, IMGPATH),
]

gamedata_map = {
    "Windows": "~/Documents/My Games/Tabletop Simulator",
    "Darwin": "~/Library/Tabletop Simulator",  # MacOS
    "Linux": "~/.local/share/Tabletop Simulator",
}
try:
    active_platform = platform.system()
    GAMEDATA_DEFAULT = os.path.expanduser(gamedata_map[active_platform])
except KeyError:
    GAMEDATA_DEFAULT = os.path.expanduser(gamedata_map["Windows"])

# If the mod location is somewhere other than the default location we can
# provide the path to the new location through a simple one-line test file
mod_link_path = os.path.join(GAMEDATA_DEFAULT, 'mod_location.txt')
if not os.path.exists(os.path.join(GAMEDATA_DEFAULT, 'Mods')
                or os.path.exists(mod_link_path)):
    print(f"Reading default gamedata directory information from: {mod_link_path}")
    if os.path.exists(mod_link_path):
        with open(os.path.join(GAMEDATA_DEFAULT, 'mod_location.txt')) as f:
            GAMEDATA_DEFAULT = f.readline().strip()
        print(f"Default gamedata directory = {GAMEDATA_DEFAULT}")
    else:
        print(f"Warning: default gamedata directory not detected, must specify at command line!")
        

class IllegalSavegameException(ValueError):
    def __init__(self):
        super().__init__("not a Tabletop Simulator savegame")


def seekURL(dic, trail=[], done=None):
    """Recursively search through the save game structure and return URLs
    and the paths to them.

    """

    if done is None:
        done = set()

    for k, v in dic.items():

        newtrail = trail + [k]

        if k == "AudioLibrary":
            for elem in v:
                try:
                    # It appears that AudioLibrary items are mappings of form
                    # “Item1” → URL, “Item2” → audio title.
                    url = elem["Item1"]
                    if url in done:
                        continue
                    done.add(url)
                    yield (newtrail, url)
                except KeyError:
                    raise NotImplementedError(
                        "AudioLibrary has unexpected structure: {}".format(v)
                    )

        elif isinstance(v, dict):
            yield from seekURL(v, newtrail, done)

        elif isinstance(v, list):
            for elem in v:
                if not isinstance(elem, dict):
                    continue
                yield from seekURL(elem, newtrail, done)

        elif k.lower().endswith("url"):
            # We don’t want tablet URLs.
            if k == "PageURL":
                continue

            # Some URL keys may be left empty.
            if not v:
                continue

            # Deck art URLs can contain metadata in curly braces
            # (yikes).
            v = re.sub(r"{.*}", "", v)
            if v in done:
                continue
            done.add(v)
            yield (newtrail, v)

        elif k == "LuaScript":
            NO_EXT_SITES = ['steamusercontent.com', 'pastebin.com', 'paste.ee', 'drive.google.com', 'steamuserimages-a.akamaihd.net',]
            # Parse lauscript for potential URLs
            url_matches = re.findall(r'((?:http|https):\/\/(?:[\w\-_]+(?:(?:\.[\w\-_]+)+))(?:[\w\-\.,@?^=%&:/~\+#]*[\w\-\@?^=%&/~\+#])?)', v)
            for url in url_matches:
                valid_url = False

                # Detect if URL ends in a valid extension or is from a site which doesn't use extension
                for site in NO_EXT_SITES:
                    if url.lower().find(site) >= 0:
                        valid_url = True
                        break
                else:
                    for ext in ALL_VALID_EXTS:
                        if url.lower().find(ext.lower()) >= 0:
                            valid_url = True
                            break

                if valid_url:
                    if url in done:
                        continue
                    done.add(url)
                    yield (newtrail, url)


# We need checks for whether a URL points to a mesh or an image, so we
# can do the right thing for each.


def is_obj(path, url):
    # TODO: None of my mods have NormalURL set (normal maps?). I’m
    # assuming these are image files.
    obj_keys = ("MeshURL", "ColliderURL")
    return path[-1] in obj_keys


def is_image(path, url):
    # This assumes that we only have mesh, assetbundle, audio, PDF and image
    # URLs.
    return not (
        is_obj(path, url)
        or is_assetbundle(path, url)
        or is_audiolibrary(path, url)
        or is_pdf(path, url)
        or is_from_script(path, url)
        or is_custom_ui_asset(path, url)
    )


def is_assetbundle(path, url):
    bundle_keys = ("AssetbundleURL", "AssetbundleSecondaryURL")
    return path[-1] in bundle_keys


def is_audiolibrary(path, url):
    audio_keys = ("CurrentAudioURL", "AudioLibrary")
    return path[-1] in audio_keys


def is_pdf(path, url):
    return path[-1] == "PDFUrl"


def is_from_script(path, url):
    return path[-1] == "LuaScript"


def is_custom_ui_asset(path, url):
    return 'CustomUIAssets' in path


def recodeURL(url):
    """Recode the given URL in the way TTS does, which yields the
    file-system path to the cached file."""

    return re.sub(r"[\W_]", "", url)


def get_fs_path_from_json_path(path, url, exts):
    recoded_name = recodeURL(url)

    for ext in exts:
        # Search the url for a valid extension
        if url.lower().find(ext.lower()) > 0:
            filename  = recoded_name + ext
            filename = os.path.join(path, filename)
            break
        else:
            # URL didn't give us any hints, so check if this file has already
            # been cached and use the extension from the cached filename
            filename = recoded_name + ext
            filename = os.path.join(path, filename)
            if os.path.exists(filename):
                break
    else:
        # This file has not been cached and extension is not included in url
        # so we don't know the extension yet. TBD when we download.
        filename = os.path.join(path, recoded_name)

    return filename


def search_cached_files(url):
    recoded_name = recodeURL(url)

    for ttsexts, path in MOD_PATHS:
        for ttsext in ttsexts:
            filename = recoded_name + ttsext
            filename = os.path.join(path, filename)
            if os.path.exists(filename):
                return filename
    else:
        return None


def get_fs_path_from_extension(url, ext):
    recoded_name = recodeURL(url)

    for ttsexts, path in MOD_PATHS:
        if ext.lower() in ttsexts:
            filename = recoded_name + ext
            filename = os.path.join(path, filename)
            return filename
    else:
        return None


def get_fs_path(path, url):
    """Return a file-system path to the object in the cache."""

    recoded_name = recodeURL(url)

    if is_from_script(path, url):
        # Can be different extensions and mod directories, so search the cache for
        # any matches.  If none are found we'll determine the file path during the
        # download process.
        filename = search_cached_files(url)
        return filename

    elif is_custom_ui_asset(path, url):
        # Can be different extensions and mod directories, so search the cache for
        # any matches.  If none are found we'll determine the file path during the
        # download process.
        filename = search_cached_files(url)
        return filename

    elif is_obj(path, url):
        filename = recoded_name + ".obj"
        return os.path.join(OBJPATH, filename)

    elif is_assetbundle(path, url):
        filename = recoded_name + ".unity3d"
        return os.path.join(BUNDLEPATH, filename)

    elif is_audiolibrary(path, url):
        # We know the cache location of the file
        # but the extension may be one of many.
        return get_fs_path_from_json_path(AUDIOPATH, url, AUDIO_EXTS)

    elif is_pdf(path, url):
        filename = recoded_name + ".PDF"
        return os.path.join(PDFPATH, filename)

    elif is_image(path, url):
        # We know the cache location of the file
        # but the extension may be one of many.
        return get_fs_path_from_json_path(IMGPATH, url, IMG_EXTS)

    else:
        errstr = (
            "Do not know how to generate path for "
            "URL {url} at {path}.".format(url=url, path=path)
        )
        raise ValueError(errstr)


def fix_ext_case(ext):
    if ext.lower() in UPPER_EXTS:
        return ext.upper()
    else:
        return ext.lower()


def urls_from_save(filename):

    with open(filename, "r", encoding="utf-8") as infile:
        try:
            save = json.load(infile, strict=False)
        except UnicodeDecodeError:
            raise IllegalSavegameException

    if not isinstance(save, dict):
        raise IllegalSavegameException

    return seekURL(save)


def get_save_name(filename):

    with open(filename, "r", encoding="utf-8") as infile:
        save = json.load(infile)
    return save["SaveName"]
