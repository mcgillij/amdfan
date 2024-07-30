# AmdFan
![Python package](https://github.com/mcgillij/amdfan/workflows/Python%20package/badge.svg)
[![Downloads](https://static.pepy.tech/personalized-badge/amdfan?period=total&units=international_system&left_color=blue&right_color=green&left_text=PyPi%20Downloads)](https://pepy.tech/project/amdfan)

Is a fork of amdgpu-fan, with security updates and added functionality.
This is intended for stand-alone GPU's and not integrated APU's.

## Why fork?

* alternatives abandoned
* lacking required features
* security fixes not addressed
* basic functionality not working

### Amdgpu_fan abandoned

As of a couple years ago, and is no longer applying any security fixes to their project or improvements. There were also some bugs that bothered me with the project when I tried to get it up and running.
Features missing

There are a number of features that I wanted, but were not available.

* Thresholds allow temperature range before changing fan speed
* Frequency setting to allow better control
* Monitoring to be able to see real-time fan speeds and temperature

### Security Fixes

There are some un-addressed pull requests for some recent YAML vulnerabilities that are still present in the old amdgpu_fan project, that I’ve addressed in this fork.

### Basic functionality

Setting the card to system managed using the amdgpu_fan pegs your GPU fan at 100%, instead of allowing the system to manage the fan settings. I fixed that bug as well in this release.

These are all addressed in Amdfan, and as long as I’ve still got some AMD cards I intend to at least maintain this for myself. And anyone’s able to help out since this is open source. I would have liked to just contribute these fixes to the main project, but it’s now inactive.

# Documentation

```help
Usage: amdfan [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --version  Show the version and exit.
  --help         Show this message and exit.

Commands:
  daemon         Run the controller as a service
  manage         Run the fan controller
  monitor        View the current temperature and speed
  print-default  Convenient defaults
  set            Manually override the fan speed
```

Each subcommand supports `--help` too, to get more details.

## Controlling the fans

There are two ways to control your fans with Amdfan. Note that in order to control the fans, you will likely need to run either approach as root. 

The recommended way is through a system service started at boot. This will control the fans based on the detected temperature at a given interval.

In case you don't want to use a service, you may also control the fans manually. While this is only advised to do when first setting up your configuration, keep in mind you can also use it to temporarily take control away from the daemon until you revert the fan speed back to `auto`.

![screenshot](https://raw.githubusercontent.com/mcgillij/amdfan/main/images/manual.png)


## Monitor

You can use Amdfan to monitor your AMD video cards using the `monitor` flag. This does not require root privileges, usually.

![screenshot](https://raw.githubusercontent.com/mcgillij/amdfan/main/images/screenshot.png)


## Configuration

Running `amdfan print-default --configuration` will dump out the default configuration that would get generated for `/etc/amdfan.yml` when you first run it as a service. If a value is not specified, it will use a default value if possible.

The following config is probably a reasonable setup:
``` bash
speed_matrix:
- [4, 4]
- [30, 33]
- [45, 50]
- [60, 66]
- [65, 69]
- [70, 75]
- [75, 89]
- [80, 100]

threshold: 4
frequency: 5

# cards:
# - card0
```

If a configuration file is not found, a default one will be generated. If you want to make any changes to the default config before running the daemon, run `amdfan print-default --configuration | sudo tee /etc/amdfan.yml` and do your changes from there.

- `speed_matrix` (required): a list of thresholds `[temperature, speed]` which are interpolated to calculate the fan speed.
- `threshold` (default `0`): allows for some leeway in temperatures, as to not constantly change fan speed
- `frequency` (default `5`): how often (in seconds) we wait between updates
- `cards` (required): a list of card names (from `/sys/class/drm`) which we want to control.

Note! You can send a **SIGHUP** signal to the daemon to request a reload of the config without restarting the whole service. Additionally, if you're using a pidfile, you can send a signal to reload the config with `amdfan daemon --signal=reload`

# Install

Users: Use your package manager to install the package. It's available on Arch Linux and Gentoo. For other distributions, please request a maintainer to bring the package to your system, or read the installation notes at your own warranty.

Maintainers: Check the [installation notes](INSTALL.md).

