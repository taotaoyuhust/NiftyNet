# -*- coding: utf-8 -*-
"""
NiftyNet launch configuration
"""


try:
    import ConfigParser as configparser
except ImportError:
    import configparser


class NiftyNetLaunchConfig(configparser.ConfigParser):
    """
    Launch configuration settings.

    This class provides the same interface and functionality
    as the built-in `ConfigParser` class. Beyond that, it
    can also parse the new YAML configuration format of
    NiftyNet. The former is for backwards compatibility only,
    while the latter is the purpose of this class' life.
    """

    def read(self, filenames, encoding=None):
        return super(NiftyNetLaunchConfig, self).read(filenames, encoding)

    def sections(self):
        return super(NiftyNetLaunchConfig, self).sections()

    def items(self, section=configparser._UNSET, raw=False, vars=None):
        return super(NiftyNetLaunchConfig, self).items(section, raw, vars)

    def add_section(self, section):
        super(NiftyNetLaunchConfig, self).add_section(section)

    def set(self, section, option, value=None):
        super(NiftyNetLaunchConfig, self).set(section, option, value)

    def remove_section(self, section):
        super(NiftyNetLaunchConfig, self).remove_section(section)

    def has_section(self, section):
        return super(NiftyNetLaunchConfig, self).has_section(section)
