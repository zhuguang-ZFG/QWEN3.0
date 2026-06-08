"""Compatibility note for the backend registry package.

Python resolves ``import backends_registry`` to the ``backends_registry/``
package in this repository. The implementation lives there after the provider
registry split; this file is kept so historical references to the old module
name do not look like a deleted source file in working trees.
"""
