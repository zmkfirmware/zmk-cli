# ZMK CLI

A command line program to help set up [ZMK Firmware](https://zmk.dev).

ZMK CLI walks you through installing ZMK and setting up a GitHub repository to store and build custom firmware. It also automates some common tasks such as adding new keyboards to your repository.

The instructions below contain commands that need to be run in a terminal program. On Windows, use the [Windows Terminal](https://apps.microsoft.com/detail/9n0dx20hk701) or PowerShell. On other operating systems, the terminal program is usually just named "Terminal".

# Installation

This readme will provide brief instructions for installing ZMK CLI. For instructions in more detail, see the [ZMK Documentation](https://zmk.dev/docs/user-setup).

## Install Git

Install Git from https://git-scm.com/downloads or your OS's package manager.

You will also need a [GitHub account](https://github.com/signup).

## Install uv

Install uv from https://docs.astral.sh/uv/getting-started/installation/.

## Install ZMK CLI

Run the following command to install ZMK CLI:

```sh
uv tool install zmk
```

If you have already installed ZMK CLI, you can update to the latest version with the following command:

```sh
uv tool upgrade zmk
```

# Usage

All ZMK CLI commands start with `zmk`. Run `zmk --help` for general usage instructions. For help with a specific subcommand, add `--help` after the subcommand, e.g. `zmk init --help`.

## Initialize a Repository

> ⚠️ If you have already created a repo and cloned it to your computer, you do not need to run this command. Set the [user.home](#userhome) setting to point to the existing repo instead.

The `zmk init` command walks you through creating a GitHub repository, then clones it to your computer so you can edit it.

Open a terminal and use the `cd` command to move to a directory where you'd like to place the ZMK files, then run `zmk init`. For example:

```sh
cd ~/Documents
zmk init
```

Follow the instructions it gives you. If you already have a ZMK config repo, select "Clone an existing repo" and enter the repo's URL, for example:

```
Repository URL: https://github.com/myusername/zmk-config
```

Otherwise, select "Create a new ZMK config repo" and it will walk you through creating a new repo.

Once you finish following all the instructions, you will have a copy of the repo stored on your computer. All `zmk` commands will run on this repo (unless the working directory is inside a different repo). If you ever forget where the repo is located, you can run `zmk cd` to find it.

Now that you have a repo created, see [Customizing ZMK](https://zmk.dev/docs/customization) for documentation on how to customize it, and see the instructions below for how ZMK CLI can automate some common tasks.

## Keyboard Management

### Add a Keyboard

To start building firmware for a new keyboard, run `zmk keyboard add`. Follow the instructions to select a keyboard (and controller board if necessary), and it will add it to the list of firmware to build and copy a default keymap into your repo.

You can then run `zmk code <keyboard>` to open the keymap in a text editor.

This command reads from a local copy of ZMK to determine the supported keyboards. If the keyboard you want to use isn't listed, try running `zmk update` to update the local copy to the latest version of ZMK. If it still isn't listed, you may be able to find a [Zephyr module](#module-management) that provides it, or you may need to [create it yourself](#create-a-new-keyboard).

### Remove a keyboard

To remove a keyboard from the build, run `zmk keyboard remove` and select the item to remove. For a split keyboard, you will need to run this twice and remove the left and right sides.

This simply removes a keyboard from the `build.yaml` file. It does not delete any `.keymap` or `.conf` files.

### List Supported Keyboards

Run `zmk keyboard list` to print a list of supported keyboard hardware.

### Create a New Keyboard

If ZMK doesn't support your keyboard yet, you can run `zmk keyboard new` to create a new keyboard from a template.

Note that this will generate most of the boilerplate for you, but you will still need to manually edit the files to match your keyboard. See the [New Keyboard Shield](https://zmk.dev/docs/development/hardware-integration/new-shield) guide for how to finish writing the keyboard files.

## Module Management

[Zephyr modules](https://docs.zephyrproject.org/4.1.0/develop/modules.html) can add support for new keyboards, behaviors, and other features to ZMK. Use the `zmk module` command to install modules into your repo:

```sh
zmk module add     # Add a module
zmk module remove  # Remove an installed module
zmk module list    # List the installed modules
zmk update         # Update the local copies of ZMK and modules to their latest versions
```

## Edit Keymap and Config Files

The `zmk code` command will open ZMK files in a text editor:

```sh
zmk code                    # Open the repo directory in an editor
zmk code <keyboard>         # Open <keyboard>.keymap in an editor
zmk code --conf <keyboard>  # Open <keyboard>.conf in an editor
zmk code --build            # Open build.yaml in an editor
```

The first time you run this command, it will ask you which editor you want to use. If you want to change this choice later or use an editor that wasn't listed, see the [core.editor](#coreeditor) and [code.explorer](#coreexplorer) settings.

## Push Changes to GitHub

Run `zmk cd` to go to the repo directory. From here, you can run `git` commands manage the repo.

For example, after adding a keyboard to your repo and editing its keymap, you can run the following commands to push your changes to GitHub and trigger a firmware build:

```sh
git add .
git commit
git push
```

You will need to [authenticate with GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github#authenticating-with-the-command-line) before the `git push` command will work. The easiest way to do this is to install the [GitHub CLI](https://cli.github.com/) and run

```sh
gh auth login
```

but you can also use a [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens). If using an access token, make sure you create it with the "workflow" scope option selected.

## Download Firmware from GitHub

After pushing changes, GitHub will automatically build the firmware for you. Run `zmk download` (or `zmk dl` for short) to open the GitHub actions page in your browser.

From this page, you can click on a build (the latest is at the top) to view its status. If the build succeeded, you can download the firmware from the "Artifacts" section at the bottom of the build summary page.

## ZMK Version Management

The `zmk version` command manages the version of ZMK you are using:

```sh
zmk version             # Print the current ZMK version
zmk version --list      # List the available versions
zmk version <revision>  # Switch to the version given by <revision>
```

You can set the revision to any Git tag, branch, or commit:

```sh
zmk version v0.3     # Switch to tag "v0.3"
zmk version main     # Switch to branch "main"
zmk version 1958217  # Switch to commit "1958217"
```

Note that `zmk version --list` will only list tagged versions.

## Configuration

The `zmk config` command manages settings for ZMK CLI:

```sh
zmk config                 # List all settings
zmk config <name>          # Print the value of the setting <name>
zmk config <name> <value>  # Set <name> to <value>
zmk config --unset <name>  # Remove the setting <name>
```

By default, these settings are stored in a file in your user profile directory. Run `zmk config --path` to get the location of this file. You can change where the settings file is stored by setting a `ZMK_CLI_CONFIG` environment variable to the new path to use, or by adding a `--config-file=<path>` argument when running `zmk`.

Other commands use the following settings:

### core.editor

Command line for a text editor to use with the `zmk code` command.

For example, to set Visual Studio Code as the editor and make it always open a new window, run:

```sh
zmk config core.editor "code --new-window"
```

### core.explorer

Command line for a file explorer to use with the `zmk code` command when opening a directory.

If this setting is not set, the `core.editor` tool will be run instead. Set this setting when using a text editor that does not support opening directories.

### user.home

The path to the repository to use whenever `zmk` is run and the working directory is not inside a ZMK config repository.

For example, to point ZMK CLI to an existing repo at `~/Documents/zmk-config`, run:

```sh
zmk config user.home ~/Documents/zmk-config
```

# Development

If you would like to help improve ZMK CLI, you can clone this repo and install it into a virtual environment where you can modify it. First, open a terminal to the root directory of the repository. Then, create a virtual environment and install the project's dependencies:

```sh
# Create virtual environment and install dependencies
uv sync
# Install pre-commit hooks
uv run prek install
```

To run the development version of the program, either prefix commands with `uv run`...

```sh
uv run zmk <args...>
```

...or [activate the virtual environment](https://docs.astral.sh/uv/pip/environments/#using-a-virtual-environment) first, and then you can use just `zmk`.

If you want `zmk` to run the development version even when you are not inside the virtual environment, you can install it globally in editable mode:

```sh
uv tool install -e .
```

## Linting

After running `uv run prek install`, linting and code formatting will be run automatically when you make a commit. You can also run these tools manually:

```sh
# lint codebase
uv run ruff check
# format files
uv run ruff format
```

Type checking is slower and difficult to configure to run as a Git commit hook, so this needs to be run manually.

```sh
uv run pyright .
```

GitHub will also run these checks and report any errors when you make a pull request.
