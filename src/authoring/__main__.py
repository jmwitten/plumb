"""Print the compact DetailSpec authoring manifest."""

from .manifest import authoring_manifest_json


def main() -> None:
    print(authoring_manifest_json(), end="")


if __name__ == "__main__":
    main()
