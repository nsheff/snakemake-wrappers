__author__ = "Johannes Köster"
__copyright__ = "Copyright 2019, Johannes Köster"
__email__ = "johannes.koester@uni-due.de"
__license__ = "MIT"

import glob
import os
import sys

if snakemake.log:
    sys.stderr = open(snakemake.log[0], "w")

from refgenie import GenomeAlias, Refgenie
from refgenie.exceptions import MissingAliasError
from refgenie.models import AssetRegistryPathComponents

genome = snakemake.params.genome
asset_group = snakemake.params.asset
# None means the asset group's default asset
asset_name = snakemake.params.get("tag")

# Refgenie finds its database via $REFGENIE_HOME_PATH or $REFGENIE_DB_CONFIG_PATH
# (default ~/.refgenie) and sets it up on first use.
rg = Refgenie()

# pull asset if necessary
alias = GenomeAlias(genome)
try:
    digest = rg.alias.resolve(alias)
    if asset_name is None:
        found = rg.asset.group.exists(asset_group, genome_digest=digest)
    else:
        found = rg.asset.exists(asset_group, asset_name, genome_digest=digest)
except MissingAliasError:
    found = False
if not found:
    # a Snakemake job cannot answer the prompt for large archives
    rg.transfer.pull(asset_group, alias, asset_name=asset_name, force_large=True)
    digest = rg.alias.resolve(alias)

for seek_key, out in snakemake.output.items():
    path = rg.asset.seek_components(
        AssetRegistryPathComponents(
            genome=genome, asset_group=asset_group, seek_key=seek_key, asset=asset_name
        ),
        force_exists=True,
    )
    _, key = rg.asset.seek_key.resolve(digest, asset_group, asset_name, seek_key)
    if key.type.value == "file":
        os.symlink(path, out)
    elif key.type.value in ("directory", "prefix"):
        # Link the files into a new directory, so that Snakemake never writes
        # into or deletes from the refgenie genome folder.
        if key.type.value == "directory":
            files = glob.glob(os.path.join(glob.escape(path), "*"))
        else:
            files = glob.glob(glob.escape(path) + "*")
        os.makedirs(out, exist_ok=True)
        for f in files:
            os.symlink(f, os.path.join(out, os.path.basename(f)))
    else:
        raise ValueError(
            f"Seek key '{seek_key}' of {genome}/{asset_group} is a "
            f"{key.type.value} value, not a path."
        )
