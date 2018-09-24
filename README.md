# ZeppelinOS bot _(zos-bot)_

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat)](https://github.com/RichardLitt/standard-readme)

[![Snap Status](https://build.snapcraft.io/badge/elopio/zos-bot.svg)](https://build.snapcraft.io/user/elopio/zos-bot)

Chat bot for ZeppelinOS.

Also known as Bib Fortuna.

## Install

In any of the [supported Linux distros](https://snapcraft.io/docs/core/install):

```
sudo snap install bibfortuna-zosbot --edge
```

## Usage

```
BIB_FORTUNA_TELEGRAM_TOKEN=${BIB_FORTUNA_TELEGRAM_TOKEN} bibfortuna-zosbot &
```

Where `${BIB_FORTUNA_TELEGRAM_TOKEN}` is the token for the Telegram bot.

### Actions

When a new user joins the ZeppelinOS Channel, the bot deletes the join
message.

### Available commands

None, yet.

## Maintainer

[@elopio](https://github.com/elopio/)

## Contribute

If you want to contribute, contact [@elopio](https://github.com/elopio/) or
open an [issue](https://github.com/elopio/zos-bot/issues).

## License

[GNU General Public License v3.0 or later](LICENSE) (C) 2018 Zeppelin
