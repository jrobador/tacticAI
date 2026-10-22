# Third-party notices

tacticAI's own code is MIT-licensed (see `LICENSE`). This repository also contains or uses the following third-party works.

## 1. Engine (`engine/`)

The match engine is based on Google Research Football (https://github.com/google-research/football), Copyright 2019 Google LLC & Bastiaan Konings, licensed under the Apache License 2.0 (`engine/LICENSE`). It has been modified by tacticAI: renamed module and identity, own teams, players, logos, kits, ball, scoreboard logo, ad boards, and a Docker build. Per-file notices are retained, and modified files are marked "Modified by the tacticAI project".

Google Research Football is in turn based on GameplayFootball by Bastiaan Konings Schuiling (https://github.com/BazkieBumpercar/GameplayFootball), dedicated to the public domain (`engine/LICENSE-public-domain-base.txt`).

## 2. Font

Alegreya Sans SC ExtraBold, Copyright 2013 The Alegreya Sans Project Authors (https://github.com/huertatipografica/Alegreya-Sans), licensed under the SIL Open Font License 1.1 (`engine/fonts/LICENSE`; copyright line in `engine/fonts/OFL-COPYRIGHT.txt`).

## 3. Container tools

These are installed in the engine's Docker image and used as external tools. They are not redistributed by this repository.

- ffmpeg (Ubuntu package, GPL), run as an external program.
- numpy (BSD).
- opencv-python-headless (Apache-2.0).
