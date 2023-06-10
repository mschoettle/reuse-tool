# SPDX-FileCopyrightText: 2017 Free Software Foundation Europe e.V. <https://fsfe.org>
# SPDX-FileCopyrightText: 2021 Alliander N.V.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""reuse is a tool for compliance with the REUSE recommendations.

Although the API is documented, it is **NOT** guaranteed stable between minor or
even patch releases. The semantic versioning of this program pertains
exclusively to the reuse CLI command. If you want to use reuse as a Python
library, you should pin reuse to an exact version.

Having given the above disclaimer, the API has been relatively stable
nevertheless, and we (the maintainers) do make some efforts to not needlessly
change the public API.
"""

import gettext
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import NamedTuple, Optional, Set, Type

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    from importlib_metadata import PackageNotFoundError, version

from boolean.boolean import Expression

try:
    __version__ = version("reuse")
except PackageNotFoundError:
    # package is not installed
    __version__ = "1.1.2"

__author__ = "Carmen Bianca Bakker"
__email__ = "carmenbianca@fsfe.org"
__license__ = "Apache-2.0 AND CC0-1.0 AND CC-BY-SA-4.0 AND GPL-3.0-or-later"
__REUSE_version__ = "3.0"

_LOGGER = logging.getLogger(__name__)

_PACKAGE_PATH = os.path.dirname(__file__)
_LOCALE_DIR = os.path.join(_PACKAGE_PATH, "locale")

if gettext.find("reuse", localedir=_LOCALE_DIR):
    gettext.bindtextdomain("reuse", _LOCALE_DIR)
    gettext.textdomain("reuse")
    _LOGGER.debug("translations found at %s", _LOCALE_DIR)
else:
    _LOGGER.debug("no translations found at %s", _LOCALE_DIR)


_IGNORE_DIR_PATTERNS = [
    re.compile(r"^\.git$"),
    re.compile(r"^\.hg$"),
    re.compile(r"^LICENSES$"),
    re.compile(r"^\.reuse$"),
]

_IGNORE_MESON_PARENT_DIR_PATTERNS = [
    re.compile(r"^subprojects$"),
]

_IGNORE_FILE_PATTERNS = [
    re.compile(r"^LICENSE"),
    re.compile(r"^COPYING"),
    # ".git" as file happens in submodules
    re.compile(r"^\.git$"),
    re.compile(r"^\.gitkeep$"),
    re.compile(r"^\.hgtags$"),
    re.compile(r".*\.license$"),
    # Workaround for https://github.com/fsfe/reuse-tool/issues/229
    re.compile(r"^CAL-1.0(-Combined-Work-Exception)?(\..+)?$"),
    re.compile(r"^SHL-2.1(\..+)?$"),
]

_IGNORE_SPDX_PATTERNS = [
    # SPDX files from
    # https://spdx.github.io/spdx-spec/conformance/#44-standard-data-format-requirements
    re.compile(r".*\.spdx$"),
    re.compile(r".*\.spdx.(rdf|json|xml|ya?ml)$"),
]

# Combine SPDX patterns into file patterns to ease default ignore usage
_IGNORE_FILE_PATTERNS.extend(_IGNORE_SPDX_PATTERNS)


class SourceType(Enum):
    """
    An enumeration representing the types of sources for license information.
    """

    #: A .license file containing license information.
    DOT_LICENSE_FILE = ".license file"
    #: A file header containing license information.
    FILE_HEADER = "file header"
    #: A .reuse/dep5 file containing license information.
    DEP5_FILE = ".reuse/dep5 file"


# TODO: In Python 3.10+, add kw_only=True
@dataclass(frozen=True)
class ReuseInfo:
    """Simple dataclass holding licensing and copyright information"""

    spdx_expressions: Set[Expression] = field(default_factory=set)
    copyright_lines: Set[str] = field(default_factory=set)
    contributor_lines: Set[str] = field(default_factory=set)
    source_path: Optional[str] = None
    source_type: Optional[SourceType] = None

    def _check_nonexistent(self, **kwargs) -> None:
        nonexistent_attributes = set(kwargs) - set(self.__dict__)
        if nonexistent_attributes:
            raise KeyError(
                f"The following attributes do not exist in"
                f" {self.__class__}: {', '.join(nonexistent_attributes)}"
            )

    def copy(self, **kwargs) -> Type["ReuseInfo"]:
        """Return a copy of ReuseInfo, replacing the values of attributes with
        the values from *kwargs*.
        """
        self._check_nonexistent(**kwargs)
        new_kwargs = {}
        for key, value in self.__dict__.items():
            new_kwargs[key] = kwargs.get(key, value)
        return self.__class__(**new_kwargs)

    def copy_union(self, **kwargs) -> Type["ReuseInfo"]:
        """Return a copy of ReuseInfo, replacing the values of Set attributes
        with sets that are the union of the existing set and the set defined in
        *kwargs*. Other attributes defined in *kwargs* are simply replaced.

        >>> old = ReuseInfo(copyright_lines={"Jane Doe"}, source_path="foo.py")
        >>> new = old.copy_union(copyright_lines={"Mr X"}, source_path="bar.py")
        >>> print(sorted(new.copyright_lines))
        ['Jane Doe', 'Mr X']
        >>> print(new.source_path)
        bar.py
        """
        self._check_nonexistent(**kwargs)
        new_kwargs = {}
        for key, value in self.__dict__.items():
            if isinstance(value, set) and kwargs.get(key):
                new_kwargs[key] = value.union(kwargs.get(key))
            else:
                new_kwargs[key] = kwargs.get(key, value)
        return self.__class__(**new_kwargs)

    def contains_copyright_or_licensing(self) -> bool:
        """Either *spdx_expressions* or *copyright_lines* is non-empty."""
        return bool(self.spdx_expressions or self.copyright_lines)

    def __bool__(self):
        return any(self.__dict__.values())


class ReuseException(Exception):
    """Base exception."""


class IdentifierNotFound(ReuseException):
    """Could not find SPDX identifier for license file."""
