# Images

## In use

| File | Where |
|---|---|
| `epixel-logo-light.png` | README header, light theme |
| `epixel-logo-dark.png` | README header, dark theme |

Both come from the product site and are switched by
`prefers-color-scheme` in the README's `<picture>` block.

## Reserved for product photography

Drop these in and the README picks them up — nothing else needs to change.
Until a file exists, do **not** reference it: a broken image in the README
reads worse than no image.

| File | What it should show | Suggested size |
|---|---|---|
| `hero.png` | The display on a desk showing a Home Assistant page | 1280 × 720 |
| `device.jpg` | Product shot on a plain background | 800 × 800 |
| `device-page.jpg` | Close photo of the screen with 4 or 6 boxes | 800 × 1200 |
| `pairing.png` | The four-digit code screen | 480 × 720 |
| `page-builder.png` | Screenshot of the Home Assistant page form | 900 × 600 |

Keep each file under about 1 MB. A product video belongs on YouTube with a link
from the README, not committed here.

### Shooting notes

The panel is glossy, so the two things that ruin a shot are **reflections** and
**moiré**.

- Light from **behind or beside the camera**, never facing the screen. Check the
  preview for your own reflection before pressing the shutter.
- Moiré: step back and zoom in slightly, and shoot at a small angle rather than
  dead-on.
- Set the display to full brightness, or the screen photographs dark against a
  lit room.
- Shoot on a plain surface. Backgrounds can be removed afterwards, but a clean
  background needs no rescue.
