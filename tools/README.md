# Dataset builders

Maintainer scripts that generate the country datasets under `geo_extension/setup/data/countries/`.
They are not part of the installed app and need only Python 3.10+ (the PSGC builder also needs `openpyxl`).

| Script | Source | Countries |
| ------ | ------ | --------- |
| `psgc/build_dataset.py` | Philippine Statistics Authority, PSGC Publication Datafile (xlsx, quarterly). Download it from https://psa.gov.ph/classification/psgc in a browser (the site blocks scripted downloads). Optional GeoNames postal codes. | `ph` |
| `geonames/build_dataset.py` + `geonames/countries.json` | GeoNames gazetteer and postal-code dumps (CC BY 4.0), downloaded automatically into `.work/`. | the 28 other countries (see `countries.json`; add more there) |
| `datagovsg/build_dataset.py` | URA Master Plan planning areas via data.gov.sg (Singapore Open Data Licence). | `sg` |

Typical refresh:

```bash
python tools/geonames/build_dataset.py us gb de id in pk bd ae sa eg ng ke za my br ca au tr mx th fr it es nl ch np lk nz --out geo_extension/setup/data/countries
python tools/psgc/build_dataset.py ~/Downloads/PSGC-2Q-2026-Publication-Datafile.xlsx --out geo_extension/setup/data/countries --postal-zip tools/geonames/.work/zip/PH.zip
python tools/datagovsg/build_dataset.py --out geo_extension/setup/data/countries
bench geo-extension validate
```

Rules the builders follow:

- Codes are the source's stable identifiers (PSGC codes, GeoNames ids, URA codes), never row numbers.
- Names are the source's display names; alternative spellings go into `aliases`. The GeoNames builder can strip type prefixes/suffixes per level (`strip`) and override single display names (`names`); the original name is kept as an alias either way.
- Postal codes are attached to the most specific unit that can be identified by name and administrative code. Anything ambiguous is dropped rather than guessed.
- Every mapping decision that is not in the source (for example Philippine independent cities listed under a province) is a named constant in the script and mentioned in the manifest description.
