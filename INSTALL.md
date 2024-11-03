# Dependencies

At build time: `autoconf`
At runtime: `python`, `numpy`, `click`, `rich` and `pyyaml`

Our standard builds use pyproject, mainly with poetry.

# Preparing the sources

The dist files are template files, which means you must first `autoconf` them. You could also just `sed` all the `.in` files if you don't want to use `autotools`.

```sh
git clone https://github.com/mcgillij/amdfan.git
cd amdfan

autoconf
./configure --prefix=/usr --libdir=/usr/lib --bindir=/usr/bin
```

# Service files

There are two ways to obtain the systemd service file. One is available during runtime, through the `amdfan --service` command, but takes some assumptions of your system. May not work.

```sh
amdfan print-default --service | sudo tee /usr/lib/systemd/system/amdfan.service
```

If you ran `./configure` successfully, you'll also find the service files for OpenRC, Runit and systemd under `dist/${init}/`.

# Configuration files

Similarly as above, you can obtain the sources from the runtime. This is not necessary, as this file is generated automatically after the daemon runs for the first time.

```bash
amdfan print-default --configuration | sudo tee /etc/amdfan.yml
```

# Executable files

The executable files are contained within amdfan. This directory is a python module, and can either be loaded as `python -m amdfan`. If you want to import the module, you may be interested in checking out `amdfan.commands`, which contains most of the subcommands.

Otherwise, just use python-exec with something like

```python
import sys
from amdfan.__main__ import main

if __name__ == '__main__':
    sys.exit(main())
```

# Installing from PyPi

You can also install amdfan from PyPi using something like poetry.

```bash
poetry init
poetry add amdfan
poetry run amdfan --help
```

# Building Python package

Requires [poetry](https://python-poetry.org/) to be installed.

```bash
git clone git@github.com:mcgillij/amdfan.git
cd amdfan/
poetry build
```

## Building Arch AUR package

Building the Arch package assumes you already have a chroot env setup to build packages.

```bash
git clone https://aur.archlinux.org/amdfan.git
cd amdfan/

autoconf --libdir=/usr
./configure
cp dist/pacman/PKGBUILD ./PKGBUILD

makechrootpkg -c -r $HOME/$CHROOT
sudo pacman -U --asdeps amdfan-*-any.pkg.tar.zst
```
