# Brand assets

Home Assistant does not read these files from the integration folder. It loads
integration artwork from **brands.home-assistant.io**, which is generated from
the [`home-assistant/brands`](https://github.com/home-assistant/brands)
repository. Until `epixel` is added there, **Devices & Services** shows a
generic placeholder next to the entry, no matter what this folder contains.

These files are prepared to the sizes that repository requires, so submitting
is a copy and a pull request rather than a design job.

| File | Size | Where it appears |
|---|---|---|
| `icon.png` | 256 × 256 | Integration tile, device page, config flow header |
| `icon@2x.png` | 512 × 512 | The same, on high-density displays |
| `logo.png` | 256 wide | Brand row in the integrations list |
| `logo@2x.png` | 512 wide | The same, on high-density displays |

The icon is the ePiXeL mark on a transparent background with 12 % padding —
Home Assistant crops tightly, and a mark that touches the edge looks clipped
next to the others.

## Submitting

1. Fork `home-assistant/brands`
2. Copy this folder to `custom_integrations/epixel/`
3. Open a pull request

The `custom_integrations/` path is the one for integrations distributed through
HACS; `core_integrations/` is for integrations shipped inside Home Assistant
and would be rejected for this one.

Review usually takes a few days. Nothing else in this repository depends on it
— the integration works fully without artwork; only the picture is missing.
