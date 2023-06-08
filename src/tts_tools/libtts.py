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

AUDIO_EXTS = ['.MP3', '.WAV', '.OGV', '.OGG']
IMG_EXTS = ['.png', '.jpg', '.mp4', '.m4v', '.webm', '.mov']
OBJ_EXTS = ['.obj']
BUNDLE_EXTS = ['.unity3d']
PDF_EXTS = ['.PDF']
TXT_EXTS = ['.TXT']

ALL_VALID_EXTS = AUDIO_EXTS + IMG_EXTS + OBJ_EXTS + BUNDLE_EXTS + PDF_EXTS + TXT_EXTS

AUDIO_KEYS = ['AudioLibrary', 'CurrentAudioURL']
IMG_KEYS = []
OBJ_KEYS = ['MeshURL', 'ColliderURL']
BUNDLE_KEYS = ['AssetbundleURL', 'AssetbundleSecondaryURL']
PDF_KEYS = ['PDFUrl']
LUA_KEYS = ['LuaScript']
TXT_KEYS = []

PATHS = [
    (AUDIO_KEYS, AUDIO_EXTS, AUDIOPATH),
    (OBJ_KEYS, OBJ_EXTS, OBJPATH),
    (BUNDLE_KEYS, BUNDLE_EXTS, BUNDLEPATH),
    (PDF_KEYS, PDF_EXTS, PDFPATH),
    (IMG_KEYS, IMG_EXTS, IMGPATH),
    (TXT_KEYS, TXT_EXTS, TXTPATH),
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


class IllegalSavegameException(ValueError):
    def __init__(self):
        super().__init__("not a Tabletop Simulator savegame")


def seekURL(dic, trail=[]):
    """Recursively search through the save game structure and return URLs
    and the paths to them.

    """

    for k, v in dic.items():

        newtrail = trail + [k]

        if k == "AudioLibrary":
            for elem in v:
                try:
                    # It appears that AudioLibrary items are mappings of form
                    # “Item1” → URL, “Item2” → audio title.
                    yield (newtrail, elem["Item1"])
                except KeyError:
                    raise NotImplementedError(
                        "AudioLibrary has unexpected structure: {}".format(v)
                    )

        elif isinstance(v, dict):
            yield from seekURL(v, newtrail)

        elif isinstance(v, list):
            for elem in v:
                if not isinstance(elem, dict):
                    continue
                yield from seekURL(elem, newtrail)

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

            yield (newtrail, v)

        elif k == "LuaScript":
            NO_EXT_SITES = ['steamusercontent.com', 'pastebin.com', 'paste.ee', 'drive.google.com']
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

def identify_filename(path, url, recoded_name, exts):
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


def get_filename_path(url, ext=None):
    # If ext is set, then lookup the appropriate directory
    # for that extension.
    # Otherwise, search in all possible directories, with all possible extensions
    # to see if a file exists
    recoded_name = recodeURL(url)

    for _, ttsexts, path in PATHS:
        if ext is None:
            for ttsext in ttsexts:
                filename = recoded_name + ttsext
                filename = os.path.join(path, filename)
                if os.path.exists(filename):
                    return filename
        else:
            if ext in ttsexts:
                filename = recoded_name + ext
                filename = os.path.join(path, filename)
                return filename

    return None


def get_fs_path(path, url):
    """Return a file-system path to the object in the cache."""

    recoded_name = recodeURL(url)

    if is_from_script(path, url):
        return get_filename_path(url)

    elif is_custom_ui_asset(path, url):
        # Custom UI assets can be various types
        return get_filename_path(url)

    elif is_obj(path, url):
        filename = recoded_name + ".obj"
        return os.path.join(OBJPATH, filename)

    elif is_assetbundle(path, url):
        filename = recoded_name + ".unity3d"
        return os.path.join(BUNDLEPATH, filename)

    elif is_audiolibrary(path, url):
        # Is the suffix always MP3, regardless of content?
        # No, it may be WAV, OGV, etc...
        return identify_filename(AUDIOPATH, url, recoded_name, AUDIO_EXTS)

    elif is_pdf(path, url):
        filename = recoded_name + ".PDF"
        return os.path.join(PDFPATH, filename)

    elif is_image(path, url):
        # TTS appears to perform some weird heuristics when determining
        # the file suffix. ._.
        return identify_filename(IMGPATH, url, recoded_name, IMG_EXTS)

    else:
        errstr = (
            "Do not know how to generate path for "
            "URL {url} at {path}.".format(url=url, path=path)
        )
        raise ValueError(errstr)


def urls_from_save(filename):

    with open(filename, "r", encoding="utf-8") as infile:
        try:
            save = json.load(infile)
        except UnicodeDecodeError:
            raise IllegalSavegameException

    if not isinstance(save, dict):
        raise IllegalSavegameException

    return seekURL(save)


def get_save_name(filename):

    with open(filename, "r", encoding="utf-8") as infile:
        save = json.load(infile)
    return save["SaveName"]
