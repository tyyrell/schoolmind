import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schoolmind.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS

base = set(TRANSLATIONS["en"])
failed = []
for language in SUPPORTED_LANGUAGES:
    keys = set(TRANSLATIONS.get(language, {}))
    missing = sorted(base - keys)
    coverage = 100 if not base else round(((len(base) - len(missing)) / len(base)) * 100, 1)
    print(f"{language}: {coverage}% ({len(base) - len(missing)}/{len(base)} keys)")
    if language in {"en", "ar"} and missing:
        failed.append(f"{language} missing required keys: {missing[:10]}")
    if coverage < 90:
        failed.append(f"{language} coverage below 90%")

if failed:
    print("Translation coverage failed:")
    for item in failed:
        print(f"- {item}")
    sys.exit(1)

print("Translation coverage passed.")
