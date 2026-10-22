# tacticAI brand assets

`source/` holds the original artwork (brand sheet, crests, kit UV maps, kit UV mask). Everything else in this folder and the engine textures are generated from it.

`tacticai-icon.png` is the tAI tile with transparent rounded corners. Use it for the favicon, the scoreboard and small UI.

`tacticai-logo-dark-bg.png` is the icon plus wordmark for dark backgrounds. `tacticai-logo-light-bg.png` is the same lockup for light backgrounds. Use them in the UI and in slides.

`crest-bka.png` (Brackenford Athletic) and `crest-wxc.png` (Wexmoor City) are the team crests trimmed to their content. Use them in the UI and in overlays.

`adboards-preview.png` shows the 5 advertising boards that go into the engine.

Palette: navy `#0C172A`, off-white `#F0F0F0`, lime `#C6F432`, BKA orange `#E8702A`, WXC teal `#1F9E9A`.

To regenerate everything (including the engine BMPs in `engine/data/`), run `python engine/tools/apply_brand.py` from the repo root (needs numpy and Pillow; `--font PATH` changes the board font, default Segoe UI Black).
