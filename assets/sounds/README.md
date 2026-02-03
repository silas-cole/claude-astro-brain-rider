# Sound Effects Library

This directory contains sound effects that the Cowboy Brain Rider can play.

## Adding Sounds
1. Find a `.wav` file (or `.mp3` if you install `mpg123` and update the code).
2. Place it in this directory.
3. Restart the `brain-rider` service.

The system will automatically detect the new file and add it to possible sound effects. To play it, the LLM just needs to output the filename (without extension) in the `sound_effect` field.

## Current Sounds
- yeehaw
- giddyup
- whip
- whoa
- laugh

## Notes
- Sounds play *before* the cowboy speaks to avoid audio device conflicts on the Raspberry Pi.
- Keep sounds short (1-2 seconds) for best experience.
