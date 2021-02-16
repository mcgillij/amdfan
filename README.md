# AmdFan

Is a fork of amdgpu-fan, with updates and using the correct settings for 'auto' / system controlled speeds.

## Usage

``` bash
Usage: amdfan.py [OPTIONS]

Options:
  --daemon   Run as daemon applying the fan curve
  --monitor  Run as a monitor showing temp and fan speed
  --manual   Manually set the fan speed value of a card
  --help     Show this message and exit.
```

## Daemon

Amdfan is also runnable as a systemd service, with the provided ```amdfan.service```.

## Monitor

You can use Amdfan to monitor your AMD video cards using the ```--monitor``` flag.

![screenshot](/images/screenshot.png)

## Manual

Alternatively if you don't want to set a fan curve, you can just apply a fan setting manually.


## Note

You will need to ```sudo``` to apply any changes to the fan speeds, but you can monitor them with regular user permissions.

# Config File example

``` yaml
# [<Temp in C>,<Fanspeed in %>]
speed_matrix:
- [4, 4]
- [30, 33]
- [45, 50]
- [60, 66]
- [65, 69]
- [70, 75]
- [75, 89]
- [80, 100]

# Current Min supported value is 4 due to driver bug
#
# Optional configuration options
#
# Allows for some leeway +/- temp, as to not constantly change fan speed
# threshold: 2
#
# Frequency will chance how often we probe for the temp
# frequency: 5
#
# cards:
# can be any card returned from `ls /sys/class/drm | grep "^card[[:digit:]]$"`
# - card0
```

## Building Python package
Requires Poetry to be installed

``` bash 
poetry build
```

## Building Arch package

Building the Arch package assumes you already have a chroot env setup to build packages.

```bash
poetry build
makechrootpkg -c -r $HOME/$CHROOT
```
